import sys
import os
import io

# Ensure the backend directory is in the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

def run_api_tests():
    print("==================================================")
    print("       AI SCAM DETECTOR: API ROUTE TESTER         ")
    print("==================================================")
    
    client = TestClient(app)

    # Helper to prepare mock file upload tuple (filename, bytes_data, content_type)
    def make_mock_file(filename: str, content: bytes = b"dummy audio content"):
        return (filename, io.BytesIO(content), "audio/wav")

    # Test Case 1: Test Direct Text Upload (OTP/Bank KYC Scam)
    print("\n[Test Case 1] Direct Text Input (Bank OTP scam):")
    response = client.post(
        "/api/v1/analyze",
        data={"text": "This is your bank manager. We need your OTP immediately to reactivate your SBI debit card."}
    )
    assert response.status_code == 200
    res_data = response.json()
    print(f"  Status: {response.status_code}")
    print(f"  Transcript: '{res_data['transcript']}'")
    print(f"  Deepfake voice probability: {res_data.get('deepfake_probability', 0.0)}")
    print(f"  Content Category: {res_data['scam_category']}")
    print(f"  Final Risk Score: {res_data['risk_score']}")
    print(f"  Security Label: {res_data['label']}")
    print(f"  Matched Advisories Count: {len(res_data['advisories'])}")

    # Test Case 2: Test Audio File Upload (Lottery Scam)
    print("\n[Test Case 2] Audio File Upload (Lottery scam filename):")
    response = client.post(
        "/api/v1/analyze",
        files={"file": make_mock_file("kbc_lottery_win_record.wav")}
    )
    assert response.status_code == 200
    res_data = response.json()
    print(f"  Status: {response.status_code}")
    print(f"  Transcript: '{res_data['transcript']}'")
    print(f"  Deepfake voice probability: {res_data.get('deepfake_probability', 0.0)}")
    print(f"  Content Category: {res_data['scam_category']}")
    print(f"  Final Risk Score: {res_data['risk_score']}")
    print(f"  Security Label: {res_data['label']}")

    # Test Case 3: Test Audio File Upload (Police threat with high AI deepfake clone indicator)
    print("\n[Test Case 3] Audio File Upload (AI deepfake + police threat):")
    response = client.post(
        "/api/v1/analyze",
        files={"file": make_mock_file("ai_synthetic_cloned_police_call.mp3")}
    )
    assert response.status_code == 200
    res_data = response.json()
    print(f"  Status: {response.status_code}")
    print(f"  Transcript: '{res_data['transcript']}'")
    print(f"  Deepfake voice probability: {res_data.get('deepfake_probability', 0.0)}")
    print(f"  Content Category: {res_data['scam_category']}")
    print(f"  Final Risk Score: {res_data['risk_score']} (Should be escalated via RiskEngine override!)")
    print(f"  Security Label: {res_data['label']} (Expected: SCAM)")

    # Test Case 4: Test Safe Voice Recording
    print("\n[Test Case 4] Audio File Upload (Safe voice recording):")
    response = client.post(
        "/api/v1/analyze",
        files={"file": make_mock_file("safe_human_lunch_plans.ogg")}
    )
    assert response.status_code == 200
    res_data = response.json()
    print(f"  Status: {response.status_code}")
    print(f"  Transcript: '{res_data['transcript']}'")
    print(f"  Deepfake voice probability: {res_data.get('deepfake_probability', 0.0)}")
    print(f"  Final Risk Score: {res_data['risk_score']}")
    print(f"  Security Label: {res_data['label']}")

    # Test Case 5: Error Handling (Missing both text and file)
    print("\n[Test Case 5] Missing Request Input parameters:")
    response = client.post("/api/v1/analyze")
    print(f"  Status: {response.status_code}")
    print(f"  Error Message Detail: {response.json()['detail']}")
    assert response.status_code == 400

    print("\n==================================================")
    print("           API ROUTE VERIFICATION PASSED          ")
    print("==================================================")

if __name__ == "__main__":
    run_api_tests()
