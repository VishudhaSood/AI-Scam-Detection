import sys
import os
import io

# Ensure the backend directory is in the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app as fastapi_app
from app.database.connection import Base, get_db
import app.database.models  # Import to register models on Base.metadata

# 1. Setup Isolated In-Memory Test Database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in test database
Base.metadata.create_all(bind=engine)

# Dependency override
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Register dependency override in FastAPI
fastapi_app.dependency_overrides[get_db] = override_get_db

def run_db_tests():
    print("==================================================")
    print("      AI SCAM DETECTOR: DATABASE INTEGRATION       ")
    print("==================================================")
    
    client = TestClient(fastapi_app)

    # Helper to prepare mock file upload tuple (filename, bytes_data, content_type)
    def make_mock_file(filename: str, content: bytes = b"dummy audio content"):
        return (filename, io.BytesIO(content), "audio/wav")

    # 1. Perform 3 different scam audits to populate the database
    print("\n[Step 1] Ingesting 3 call analyses...")
    
    # Audit 1: OTP/KYC text scan
    r1 = client.post(
        "/api/v1/analyze",
        data={"text": "Please share your account card OTP to avoid account suspension immediately."}
    )
    assert r1.status_code == 200
    print("  Ingested Audit 1: Bank KYC text threat")

    # Audit 2: Lottery audio file scan
    r2 = client.post(
        "/api/v1/analyze",
        files={"file": make_mock_file("lucky_draw_winner.wav")}
    )
    assert r2.status_code == 200
    print("  Ingested Audit 2: Lottery audio call")

    # Audit 3: Normal/Safe audio file scan
    r3 = client.post(
        "/api/v1/analyze",
        files={"file": make_mock_file("safe_human_chat.ogg")}
    )
    assert r3.status_code == 200
    print("  Ingested Audit 3: Safe human conversation")

    # 2. Fetch history and verify persistence
    print("\n[Step 2] Retrieving scan history from database...")
    response = client.get("/api/v1/analyze/history")
    assert response.status_code == 200
    
    history = response.json()
    print(f"  Retrieved history list size: {len(history)} (Expected: 3)")
    assert len(history) == 3

    # 3. Verify ordering and structure (most recent first)
    print("\n[Step 3] Verifying database records structure and sorting...")
    
    # The last ingested scan (Safe human conversation) should be the first in history
    first_record = history[0]
    print(f"  First Record in History -> Transcript: '{first_record['transcript']}'")
    print(f"  First Record in History -> Category: {first_record['scam_category']}")
    print(f"  First Record in History -> Label: {first_record['label']} (Expected: SAFE)")
    assert first_record["label"] == "SAFE"

    # The second record should be the Lottery scan
    second_record = history[1]
    print(f"  Second Record in History -> Category: {second_record['scam_category']} (Expected: Lottery & Prize Scam)")
    assert second_record["scam_category"] == "Lottery & Prize Scam"

    # The third record should be the Bank KYC scan
    third_record = history[2]
    print(f"  Third Record in History -> Label: {third_record['label']} (Expected: SCAM)")
    assert third_record["label"] == "SCAM"

    print("\n==================================================")
    print("          DATABASE INTEGRATION PASSED             ")
    print("==================================================")

    # Clean up overrides
    fastapi_app.dependency_overrides.clear()

if __name__ == "__main__":
    run_db_tests()
