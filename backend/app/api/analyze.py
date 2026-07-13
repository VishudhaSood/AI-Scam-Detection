from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Depends
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.schemas import AnalysisResponse
from app.services.analyzer import AnalyzerService
from app.services.whisper_service import WhisperService
from app.services.risk_engine import RiskEngine
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

    # 2. Extract or Transcribe Audio
    analysis_text = ""
    deepfake_prob = 0.0
    
    if text:
        analysis_text = text
        # Direct text inputs have no deepfake voice biometric context
        deepfake_prob = 0.05
    elif file:
        # Check the file extension just to ensure it's a valid media format
        filename = file.filename.lower()
        if not any(filename.endswith(ext) for ext in [".wav", ".mp3", ".m4a", ".ogg", ".webm"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file.filename}'. Please upload an audio file (WAV, MP3, M4A, OGG, WEBM)."
            )
        
        # Call WhisperService to transcribe and compute deepfake likelihood
        analysis_text = await WhisperService.transcribe_audio(file)
        deepfake_prob = await WhisperService.detect_deepfake(file)

    # 3. Invoke Domain Service for content and advisory evaluation
    response = AnalyzerService.analyze_transcript(analysis_text)
    
    # 4. Compute combined risk and label via Risk Engine
    combined_risk, final_label = RiskEngine.calculate_combined_risk(deepfake_prob, response.risk_score)
    
    # Update response object with unified metrics
    response.risk_score = combined_risk
    response.label = final_label
    response.deepfake_probability = deepfake_prob

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


