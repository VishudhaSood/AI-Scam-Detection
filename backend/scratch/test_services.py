import asyncio
import io
import sys
import os

# Ensure the backend directory is in the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import UploadFile
from app.services.whisper_service import WhisperService
from app.services.risk_engine import RiskEngine

async def run_tests():
    print("==================================================")
    print("       AI SCAM DETECTOR: SERVICE TEST RUNNER      ")
    print("==================================================")
    
    # Helper to create a mock UploadFile
    def create_mock_upload_file(filename: str, dummy_bytes: bytes = b"dummy audio content") -> UploadFile:
        file_like = io.BytesIO(dummy_bytes)
        return UploadFile(filename=filename, file=file_like)

    # Test Cases for WhisperService & Deepfake detection
    test_audios = [
        ("kbc_lottery_call_2026.wav", "Lottery Scam Scenario"),
        ("sbi_kyc_otp_alert.mp3", "Bank OTP/KYC Scenario"),
        ("mumbai_police_threat.m4a", "Customs/Police Scenario"),
        ("real_human_safe_call.ogg", "Safe Human Scenario"),
        ("synthetic_ai_cloned_voice.wav", "AI Deepfake Voice Scenario")
    ]

    print("\n--- Testing WhisperService (Transcription & Deepfake check) ---")
    for filename, description in test_audios:
        print(f"\n[Test Case] {description} ({filename}):")
        
        # Instantiate file
        mock_file = create_mock_upload_file(filename)
        
        # Test Transcription
        transcript = await WhisperService.transcribe_audio(mock_file)
        print(f"  Transcript: '{transcript}'")
        
        # Test Deepfake
        deepfake_prob = await WhisperService.detect_deepfake(mock_file)
        print(f"  Deepfake Probability: {deepfake_prob} (Is AI: {deepfake_prob >= 0.7})")

    # Test Cases for RiskEngine
    print("\n--- Testing RiskEngine (Risk Combination & Classification) ---")
    risk_scenarios = [
        (0.10, 0.10, "Low Deepfake & Low Content Risk (Safe)"),
        (0.85, 0.20, "High Deepfake but Low Content Risk (Suspicious)"),
        (0.15, 0.90, "Low Deepfake but High Content Risk (Scam)"),
        (0.85, 0.60, "High Deepfake + Moderate Content Risk (SCAM Escalation Override)"),
        (0.05, 0.98, "Extreme Content Risk (SCAM Escalation Override)"),
        (0.92, 0.92, "High Deepfake + High Content Risk (Scam)")
    ]

    for deepfake_p, llm_risk, desc in risk_scenarios:
        final_risk, label = RiskEngine.calculate_combined_risk(deepfake_p, llm_risk)
        print(f"\n[Scenario] {desc}:")
        print(f"  Inputs -> Voice: {deepfake_p}, LLM: {llm_risk}")
        print(f"  Outputs -> Final Risk Score: {final_risk}, Label: {label}")

    print("\n==================================================")
    print("             ALL TEST SCENARIOS COMPLETED          ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
