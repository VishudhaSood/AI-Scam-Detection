from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from app.database.connection import Base

class CallLog(Base):
    """
    SQLAlchemy model representing a saved call scam audit result.
    """
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transcript = Column(Text, nullable=False)
    risk_score = Column(Float, nullable=False)
    label = Column(String(50), nullable=False)  # SAFE, SUSPICIOUS, SCAM
    scam_category = Column(String(100), nullable=False)
    deepfake_probability = Column(Float, nullable=True)
    explanation = Column(Text, nullable=False)
    session_id = Column(String(100), nullable=True)
    caller_number = Column(String(50), nullable=True)
    duration_s = Column(Float, nullable=True)
    peak_risk = Column(Float, nullable=True)
    score_timeline = Column(Text, nullable=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Persisted cybercrime-complaint draft (M9 persistence pass). The AI body is
    # generated once, sealed by report_hash, and reused on every reopen so the
    # document — and its hash — stay fixed instead of being re-written by the LLM
    # each time the modal opens. report_version bumps on an explicit Regenerate.
    # All NULL until the first report is generated for this call.
    report_text = Column(Text, nullable=True)
    report_hash = Column(String(64), nullable=True)
    report_version = Column(Integer, nullable=True)
    report_generated_at = Column(DateTime, nullable=True)
