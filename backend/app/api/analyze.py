from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Depends
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool
from app.models.schemas import AnalysisResponse, EvidenceBreakdown, ReportRequest
from app.services.analyzer import AnalyzerService
from app.services.whisper_service import WhisperService
from app.services.risk_engine import EvidenceFusionEngine, AdaptiveRiskEngine
from app.services.heuristic_scorer import HeuristicScorer
from app.rag.query_engine import RAGQueryEngine
from app.services.report_generator import ReportGenerator
from app.database.connection import get_db
from app.database import crud
from app.auth.deps import get_current_user_optional
from app.database.models import User

router = APIRouter(prefix="/analyze", tags=["Analysis"])

@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_call(
    text: Optional[str] = Form(None, description="Direct text input of the transcript to analyze."),
    file: Optional[UploadFile] = File(None, description="Recorded audio file of the phone call."),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> AnalysisResponse:
    """
    Analyzes a voice call transcript or audio file for potential AI scam markers.
    Accepts text or audio upload. If audio is uploaded, uses Whisper to transcribe it.
    Saves the audit log in the database.
    """
    # 1. Input Validation
    if not text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a 'text' transcript or a 'file' audio upload must be provided."
        )

    # 2. Extract or Transcribe Audio
    analysis_text = ""
    content = None

    if file:
        # Check the file extension just to ensure it's a valid media format
        filename = file.filename.lower()
        if not any(filename.endswith(ext) for ext in [".wav", ".mp3", ".m4a", ".ogg", ".webm"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file.filename}'. Please upload an audio file (WAV, MP3, M4A, OGG, WEBM)."
            )
        
        # Read raw bytes FIRST before Whisper consumes the file stream
        content = await file.read()
        await file.seek(0)
        
        # Call WhisperService to transcribe
        analysis_text = await WhisperService.transcribe_audio(file)
    else:
        analysis_text = text

    # 3. Invoke Domain Service for content and advisory evaluation
    response = AnalyzerService.analyze_transcript(analysis_text)
    
    # 4. Compute combined risk and label via Evidence Orchestrator
    from app.services.evidence_orchestrator import EvidenceOrchestrator
    
    # Create a temporary state-holding class representing session state to satisfy providers
    class TempSession:
        def __init__(self):
            self.llm_audits_done = 1
            self.last_llm_risk = response.risk_score
            self.llm_scam_category = response.scam_category
            self.llm_red_flags = []
            self.pending_questions = []
            self.llm_suggested_questions = []
            self.llm_safe_actions = []
            self.llm_advisories = response.advisories
            self.llm_verdict = "N/A"
            self.last_audit_word_count = len(analysis_text.split())
            self.last_llm_audit_time = 0.0
            # The orchestrator's session path runs the stateful engine; a fresh
            # one on its first cycle passes the fused score through unchanged
            self.risk_engine = AdaptiveRiskEngine()
            # This is a one-shot analysis: there is no multi-turn caller-verification
            # loop here, so the verification dimension can never contribute. Lets
            # fuse_evidence renormalize it away instead of wasting 10% of the score
            # budget on a signal that structurally never fires for batch input.
            self.verification_available = False

    temp_session = TempSession()
    
    orchestrator = EvidenceOrchestrator()
    context = {
        "session": temp_session,
        "transcript": analysis_text,
        "audio_data": content if file else None,
        "filename": file.filename if file else None
    }
    
    eval_result = await orchestrator.evaluate(context)
    
    # Update response object with unified metrics and evidence breakdown
    response.risk_score = eval_result["risk_smoothed"]
    response.label = "SCAM" if eval_result["risk_smoothed"] >= 0.75 else "SUSPICIOUS" if eval_result["risk_smoothed"] >= 0.40 else "SAFE"
    response.evidence_breakdown = EvidenceBreakdown(**eval_result["evidence_breakdown"])
    response.overall_confidence = eval_result["confidence"]
    import json
    response.reasoning_trace = eval_result["reasoning_trace"]
    response.score_timeline = json.dumps([0.05, round(eval_result["risk_smoothed"], 3)])

    # 5. Persist the log in the database, and surface its id so the frontend can
    #    later request a complaint draft that is cached against this exact call.
    saved = crud.save_analysis_result(db, response, user_id=user.id if user else None)
    response.id = saved.id

    return response

@router.get("/history", response_model=List[AnalysisResponse], status_code=status.HTTP_200_OK)
async def get_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> List[AnalysisResponse]:
    """
    Retrieves the history of call scan audits.

    Reads stored fields only — does not re-run a full LLM analysis per row.
    That used to call AnalyzerService.analyze_transcript() (an LLM audit) for
    every saved log just to fetch advisories, burning API quota on every
    drawer open and leaving evidence_breakdown/overall_confidence as a fresh,
    unrelated re-analysis that could visibly disagree with the stored label
    (FLAWS_AND_IMPROVEMENTS.md §2.9). Advisories are still looked up, but via
    the local vector-store query only (no LLM call).
    """
    db_logs = crud.get_analysis_history(db, limit=limit, user_id=user.id if user else None)

    results = []
    for log in db_logs:
        advisories = RAGQueryEngine.query_advisories(log.transcript)
        results.append(AnalysisResponse(
            id=log.id,
            transcript=log.transcript,
            risk_score=log.risk_score,
            label=log.label,
            scam_category=log.scam_category,
            explanation=log.explanation,
            advisories=advisories,
            session_id=log.session_id,
            caller_number=log.caller_number,
            duration_s=log.duration_s,
            peak_risk=log.peak_risk,
            score_timeline=log.score_timeline,
            analyzed_at=log.analyzed_at
        ))

    return results


@router.post("/generate-report", status_code=status.HTTP_200_OK)
async def generate_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """
    Returns a fact-constrained complaint/audit document plus its SHA-256 seal.

    The document's nature follows the verdict: SCAM/SUSPICIOUS produces a
    cybercrime complaint draft, SAFE a neutral CALL AUDIT RECORD (ReportGenerator
    decides from the label). The schema requires a transcript, so an empty body
    is a 422 rather than a complaint drafted about nothing.

    Persistence: when `log_id` names a saved call, the draft is generated once and
    stored; every later open returns that exact stored document (no LLM call, so
    the text and its seal never drift). `regenerate=true` overwrites it with a new
    sealed version. Mid-call drafts (no `log_id`) are generated fresh and not
    stored, since the call is not yet persisted.
    """
    payload = request.model_dump()

    # Persisted path: a saved call we can cache the draft against.
    if request.log_id is not None:
        log = crud.get_call_log(db, request.log_id)
        if log is not None:
            # Ownership: a report may be drafted/read only for your own call or an
            # anonymous (unowned) one — never another account's call.
            if log.user_id is not None and (user is None or log.user_id != user.id):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "This audit belongs to another account.")
            if log.report_text and not request.regenerate:
                # Stored draft — return it unchanged. No LLM call; stable hash.
                return {
                    "report_text": log.report_text,
                    "sha256_hash": log.report_hash or "",
                    "report_version": log.report_version or 1,
                    "cached": True,
                }
            # First generation for this call, or an explicit Regenerate: bump the
            # version, generate deterministically, store, and return.
            new_version = (log.report_version or 0) + 1
            payload["report_version"] = new_version
            result = await ReportGenerator.generate_report(payload)
            crud.save_report(db, request.log_id, result["report_text"], result["sha256_hash"], new_version)
            result["report_version"] = new_version
            result["cached"] = False
            return result

    # Ephemeral path: mid-call draft, or a call with no saved row. Generate fresh,
    # do not store — there is no persisted call to key the document to yet.
    payload["report_version"] = 1
    result = await ReportGenerator.generate_report(payload)
    result["report_version"] = 1
    result["cached"] = False
    return result
