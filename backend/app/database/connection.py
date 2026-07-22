import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Define database file path relative to backend folder
DATABASE_URL = "sqlite:///./db.sqlite3"

# Create the SQLAlchemy engine
# connect_args={"check_same_thread": False} is required only for SQLite
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative database models
Base = declarative_base()

from sqlalchemy import inspect, text

def init_db():
    """
    Initializes tables and ensures missing schema columns are auto-migrated
    for existing local SQLite databases.
    """
    Base.metadata.create_all(bind=engine)
    try:
        # Seed the demo account once (idempotent). Its id anchors the one-time
        # backfill of pre-account call logs below. Local import avoids an
        # app.auth <-> app.database import cycle.
        from app.auth.security import hash_password
        demo_email = "demo@aiscamguard.local"
        with engine.begin() as conn:
            conn.execute(
                text("INSERT OR IGNORE INTO users (email, password_hash, created_at) "
                     "VALUES (:email, :ph, :now)"),
                {"email": demo_email, "ph": hash_password("demo1234"),
                 "now": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")},
            )
            row = conn.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": demo_email},
            ).fetchone()
            demo_id = row[0] if row else None

        inspector = inspect(engine)
        if "call_logs" in inspector.get_table_names():
            existing_cols = {c["name"] for c in inspector.get_columns("call_logs")}
            with engine.begin() as conn:
                if "session_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN session_id TEXT"))
                if "caller_number" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN caller_number TEXT"))
                if "duration_s" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN duration_s REAL"))
                if "peak_risk" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN peak_risk REAL"))
                if "score_timeline" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN score_timeline TEXT"))
                if "report_text" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN report_text TEXT"))
                if "report_hash" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN report_hash TEXT"))
                if "report_version" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN report_version INTEGER"))
                if "report_generated_at" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN report_generated_at DATETIME"))
                if "user_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE call_logs ADD COLUMN user_id INTEGER"))
                    # One-time: rows that predate accounts become the demo user's
                    # history. This branch runs only on the migration that first
                    # adds user_id, so later anonymous scans (NULL) are never
                    # swept into demo.
                    if demo_id is not None:
                        conn.execute(
                            text("UPDATE call_logs SET user_id = :uid WHERE user_id IS NULL"),
                            {"uid": demo_id},
                        )
    except Exception as e:
        print(f"Database migration notice: {e}")

def get_db():
    """
    FastAPI dependency that yields a database session and ensures
    the connection is closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
