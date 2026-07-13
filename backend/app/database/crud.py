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
        deepfake_probability=response_data.deepfake_probability,
        explanation=response_data.explanation,
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
