from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class AnalysisRequest(BaseModel):
    """
    Schema representing a request to analyze a transcript text directly.
    Useful for testing or text-based inputs.
    """
    text: str = Field(..., description="The raw transcript text to analyze for scam patterns.")
    session_id: Optional[str] = Field(None, description="Optional unique identifier for the call session.")

class Advisory(BaseModel):
    """
    Schema for a retrieved regulatory advisory (RBI, CERT-In, etc.).
    """
    title: str = Field(..., description="Title of the advisory.")
    source: str = Field(..., description="Source agency, e.g., RBI, CERT-In.")
    description: str = Field(..., description="Summary details of the warning or advisory.")
    url: Optional[str] = Field(None, description="Direct link to the official advisory source.")

class AnalysisResponse(BaseModel):
    """
    Schema representing the complete analysis result of a call.
    """
    transcript: str = Field(..., description="The analyzed transcript text.")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Risk level from 0.0 (safe) to 1.0 (high scam risk).")
    label: str = Field(..., description="Safety label: SAFE, SUSPICIOUS, or SCAM.")
    scam_category: str = Field(..., description="Detected scam category (e.g., Bank Impersonation, Lottery, None).")
    deepfake_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of synthetic voice generation.")
    explanation: str = Field(..., description="LLM-generated explanation of why the call was classified this way.")
    advisories: List[Advisory] = Field(default=[], description="List of matched RBI or CERT-In advisories from RAG.")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of when the analysis was performed.")
