from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from app.database.connection import Base


class User(Base):
    """A registered account. Login is optional (see anonymous-allowed model), so a
    CallLog may or may not reference one."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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

    # Owner of this audit. NULL = anonymous (a scan run while logged out); every
    # logged-in scan carries the user id so history can be filtered per-account.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
