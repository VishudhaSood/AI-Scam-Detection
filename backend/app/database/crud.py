from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models import CallLog
from app.models.schemas import AnalysisResponse

def save_analysis_result(db: Session, response_data: AnalysisResponse) -> CallLog:
    """
    Saves an AnalysisResponse audit result into the database.
    """
    db_log = CallLog(
        transcript=response_data.transcript,
        risk_score=response_data.risk_score,
        label=response_data.label,
        scam_category=response_data.scam_category,
        # Stays NULL = "not checked". Voice-spoof detection (AASIST) was removed
        # from the pipeline, so nothing measures this. Writing 0.0 would assert
        # "we checked and it is not synthetic", which we cannot support.
        deepfake_probability=getattr(response_data, "deepfake_probability", None),
        explanation=response_data.explanation,
        session_id=getattr(response_data, "session_id", None),
        caller_number=getattr(response_data, "caller_number", None),
        duration_s=getattr(response_data, "duration_s", None),
        peak_risk=getattr(response_data, "peak_risk", None),
        score_timeline=getattr(response_data, "score_timeline", None),
        analyzed_at=response_data.analyzed_at
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_analysis_history(db: Session, limit: int = 50) -> list[CallLog]:
    """
    Fetches the history of audited calls, sorted by the most recent first.
    """
    return db.query(CallLog).order_by(CallLog.analyzed_at.desc()).limit(limit).all()

def get_call_log(db: Session, log_id: int) -> CallLog | None:
    """
    Fetches a single saved call by its primary key, or None if it does not exist.
    Used by the report endpoint to look up any already-stored complaint draft.
    """
    return db.query(CallLog).filter(CallLog.id == log_id).first()

def save_report(db: Session, log_id: int, report_text: str, report_hash: str, version: int) -> CallLog | None:
    """
    Persists a generated complaint draft against its call so future opens return
    the stored document instead of re-invoking the LLM. `version` is the new
    report version (1 on first generation, bumped on each explicit Regenerate).
    Returns the updated row, or None if the call id does not exist.
    """
    log = db.query(CallLog).filter(CallLog.id == log_id).first()
    if log is None:
        return None
    log.report_text = report_text
    log.report_hash = report_hash
    log.report_version = version
    log.report_generated_at = datetime.utcnow()
    db.commit()
    db.refresh(log)
    return log
