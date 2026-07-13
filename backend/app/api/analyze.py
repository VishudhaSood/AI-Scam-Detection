from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status
from typing import Optional
from app.models.schemas import AnalysisResponse
from app.services.analyzer import AnalyzerService

router = APIRouter(prefix="/analyze", tags=["Analysis"])

@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_call(
    text: Optional[str] = Form(None, description="Direct text input of the transcript to analyze."),
    file: Optional[UploadFile] = File(None, description="Recorded audio file of the phone call.")
) -> AnalysisResponse:
    """
    Analyzes a voice call transcript or audio file for potential AI scam markers.
    Accepts text or audio upload. If audio is uploaded, simulates a Whisper transcription.
    """
    # 1. Input Validation
    if not text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a 'text' transcript or a 'file' audio upload must be provided."
        )

    # 2. Extract or Simulate Transcription
    analysis_text = ""
    if text:
        analysis_text = text
    elif file:
        # Simulate speech-to-text (Whisper stage in future milestones)
        # We check the file extension just to ensure it's a valid mock media format
        filename = file.filename.lower()
        if not any(filename.endswith(ext) for ext in [".wav", ".mp3", ".m4a", ".ogg", ".webm"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file.filename}'. Please upload an audio file (WAV, MP3, M4A, OGG, WEBM)."
            )
        
        # We generate a simulated transcription based on a mock scan
        analysis_text = (
            "Hello, this is officer Vikram from the Mumbai Police Headquarters. "
            "An illegal package with custom violations was intercepted in your name. "
            "Please confirm your identity and bank details immediately to avoid arrest."
        )

    # 3. Invoke Domain Service
    response = AnalyzerService.analyze_transcript(analysis_text)
    return response
