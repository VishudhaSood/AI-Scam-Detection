from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime
from enum import Enum

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


# ---------------------------------------------------------------------------
# Live Call Guardian — WebSocket contract (Phase 2, NEW_ARCHITECTURE.md §4)
#
# Every JSON text frame on WS /api/v1/ws/live carries a "type" field that
# identifies which of the models below it is. Binary frames (raw webm audio
# chunks) carry no envelope. This file is the single source of truth for the
# protocol: Dev 2 (LiveSession) and Dev 3 (audit engine) build against these
# models and must not redefine them locally.
# ---------------------------------------------------------------------------

class LiveMode(str, Enum):
    """
    Coaching state machine modes (NEW_ARCHITECTURE.md §6). Server-computed;
    the UI only renders what it is told.
    """
    MONITOR = "MONITOR"
    VERIFY = "VERIFY"
    DANGER = "DANGER"


class RiskLabel(str, Enum):
    """
    Classification labels shared by the batch and live paths.
    """
    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    SCAM = "SCAM"


class LiveStart(BaseModel):
    """
    Client -> Server. First frame of a live session.
    """
    type: Literal["start"] = "start"
    caller_number: Optional[str] = Field(None, description="User-entered caller number, used later in the complaint draft.")


class LiveEnd(BaseModel):
    """
    Client -> Server. Graceful end of a live session; triggers finalization.
    """
    type: Literal["end"] = "end"


class LiveUpdate(BaseModel):
    """
    Server -> Client. Pushed after each processing cycle (~every 5s).
    Milestone 7 fills session_id, elapsed_s, transcripts, and risk_raw;
    the remaining fields keep their defaults until Milestone 8 wires the
    adaptive risk engine and incremental LLM audit.
    """
    type: Literal["update"] = "update"
    session_id: str = Field(..., description="Server-generated UUID identifying this live session.")
    elapsed_s: float = Field(..., ge=0.0, description="Seconds elapsed since the session started.")
    transcript_committed: str = Field("", description="Finalized transcript text; never changes once sent.")
    transcript_partial: str = Field("", description="Live tail of the transcript; may be revised next cycle.")
    risk_raw: float = Field(0.0, ge=0.0, le=1.0, description="Unsmoothed per-cycle risk (heuristic/LLM blend).")
    risk_smoothed: float = Field(0.0, ge=0.0, le=1.0, description="EMA-smoothed, ratcheted display score (M8).")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="How much evidence backs the score (M8).")
    label: RiskLabel = Field(RiskLabel.SAFE, description="Classification of the call so far.")
    mode: LiveMode = Field(LiveMode.MONITOR, description="Coach state machine mode (M8).")
    scam_category: str = Field("None", description="Detected scam category, if any.")
    red_flags: List[str] = Field(default=[], description="Accumulated red flags spotted by the LLM audit (M8).")
    suggested_questions: List[str] = Field(default=[], description="Verification questions; non-empty only in VERIFY mode (M8).")
    safe_actions: List[str] = Field(default=[], description="Defensive prompts; non-empty only in DANGER mode (M8).")
    advisories: List[Advisory] = Field(default=[], description="Matched advisories from RAG retrieval.")


class LiveFinal(AnalysisResponse):
    """
    Server -> Client. Last frame of a session: the standard AnalysisResponse
    (same shape the batch /analyze path returns) plus live-session extras.
    """
    type: Literal["final"] = "final"
    session_id: str = Field(..., description="UUID of the live session that just ended.")
    log_id: Optional[int] = Field(None, description="Database id of the persisted CallLog row (M9).")
