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
