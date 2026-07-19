from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Depends
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool
from app.models.schemas import AnalysisResponse, EvidenceBreakdown
from app.services.analyzer import AnalyzerService
from app.services.whisper_service import WhisperService
from app.services.deepfake_detector import AASISTDetector, DeepfakeResult
from app.services.risk_engine import EvidenceFusionEngine
from app.services.heuristic_scorer import HeuristicScorer
from app.database.connection import get_db
from app.database import crud

router = APIRouter(prefix="/analyze", tags=["Analysis"])

@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_call(
    text: Optional[str] = Form(None, description="Direct text input of the transcript to analyze."),
    file: Optional[UploadFile] = File(None, description="Recorded audio file of the phone call."),
    db: Session = Depends(get_db)
) -> AnalysisResponse:
    """
    Analyzes a voice call transcript or audio file for potential AI scam markers.
    Accepts text or audio upload. If audio is uploaded, uses Whisper to transcribe it
    and evaluates it for synthetic voice clone (deepfake) biometrics.
    Saves the audit log in the database.
    """
    # 1. Input Validation
    if not text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a 'text' transcript or a 'file' audio upload must be provided."
        )

    # 2. Extract or Transcribe Audio & Run AASIST Deepfake Detector
    analysis_text = ""
    
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
        
        # Call AASISTDetector with the already-read bytes + transcript
        df_result = await run_in_threadpool(AASISTDetector.detect, content, file.filename, analysis_text)
    else:
        analysis_text = text
        # Direct text inputs have no deepfake voice biometric context
        df_result = DeepfakeResult(probability=None, label=None, confidence=None, model="AASIST", latency_ms=0.0)

    # 3. Invoke Domain Service for content and advisory evaluation
    response = AnalyzerService.analyze_transcript(analysis_text)
    
    # 4. Compute combined risk and label via Evidence Fusion Engine
    heuristic_risk = HeuristicScorer.score(analysis_text).risk
    advisories_count = len(response.advisories)
    
    combined_risk, breakdown = EvidenceFusionEngine.fuse_evidence(
        transcript_risk=response.risk_score,
        deepfake_prob=df_result.probability,
        heuristic_risk=heuristic_risk,
        advisories_count=advisories_count,
        verification_verdict="N/A"
    )
    
    # Update response object with unified metrics and evidence breakdown
    response.risk_score = combined_risk
    response.label = "SCAM" if combined_risk >= 0.75 else "SUSPICIOUS" if combined_risk >= 0.40 else "SAFE"
    response.deepfake_probability = df_result.probability
    response.deepfake_label = df_result.label
    response.deepfake_confidence = df_result.confidence
    response.deepfake_model = df_result.model
    response.evidence_breakdown = EvidenceBreakdown(**breakdown)
    response.overall_confidence = min(1.0, len(analysis_text.split()) / 120.0)

    # 5. Persist the log in the database
    crud.save_analysis_result(db, response)
    
    return response

@router.get("/history", response_model=List[AnalysisResponse], status_code=status.HTTP_200_OK)
async def get_history(
    limit: int = 20,
    db: Session = Depends(get_db)
) -> List[AnalysisResponse]:
    """
    Retrieves the history of call scan audits.
    """
    db_logs = crud.get_analysis_history(db, limit=limit)
    
    # Convert database models back to schemas and enrich them with advisories dynamically
    results = []
    for log in db_logs:
        response = AnalyzerService.analyze_transcript(log.transcript)
        response.risk_score = log.risk_score
        response.label = log.label
        response.scam_category = log.scam_category
        response.deepfake_probability = log.deepfake_probability
        response.explanation = log.explanation
        response.analyzed_at = log.analyzed_at
        results.append(response)
        
    return results


