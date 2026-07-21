import os
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
