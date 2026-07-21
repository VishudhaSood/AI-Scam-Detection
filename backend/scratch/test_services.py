import asyncio
import io
import sys
import os

# Ensure the backend directory is in the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import UploadFile
from app.services.whisper_service import WhisperService
from app.services.whisper_service import WhisperService
from app.services.risk_engine import EvidenceFusionEngine, AdaptiveRiskEngine

async def run_tests():
    print("==================================================")
    print("       AI SCAM DETECTOR: SERVICE TEST RUNNER      ")
    print("==================================================")
    
    # Helper to create a mock UploadFile
    def create_mock_upload_file(filename: str, dummy_bytes: bytes = b"dummy audio content") -> UploadFile:
        file_like = io.BytesIO(dummy_bytes)
        return UploadFile(filename=filename, file=file_like)

    # Test Cases for WhisperService
    test_audios = [
        ("kbc_lottery_call_2026.wav", "Lottery Scam Scenario"),
        ("sbi_kyc_otp_alert.mp3", "Bank OTP/KYC Scenario"),
        ("mumbai_police_threat.m4a", "Customs/Police Scenario"),
        ("real_human_safe_call.ogg", "Safe Human Scenario")
    ]

    print("\n--- Testing WhisperService (Transcription check) ---")
    for filename, description in test_audios:
        print(f"\n[Test Case] {description} ({filename}):")
        
        # Instantiate file
        mock_file = create_mock_upload_file(filename)
        
        # Test Transcription
        transcript = await WhisperService.transcribe_audio(mock_file)
        print(f"  Transcript: '{transcript}'")

    # Test Cases for EvidenceFusionEngine & AdaptiveRiskEngine
    print("\n--- Testing EvidenceFusionEngine (Evidence Fusion & Classification) ---")
    risk_scenarios = [
        (0.10, 0.10, 0, "N/A", "Low Risk (Safe)"),
        (0.85, 0.80, 2, "EVASIVE", "High Risk Bank Impersonation (SCAM)"),
        (0.45, 0.40, 1, "N/A", "Suspicious Claims (SUSPICIOUS)"),
        (0.95, 0.90, 3, "THREATENED", "Digital Arrest Threat (SCAM)")
    ]

    for t_risk, h_risk, adv_count, verdict, desc in risk_scenarios:
        fused_score, breakdown = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=t_risk,
            heuristic_risk=h_risk,
            advisories_count=adv_count,
            verification_verdict=verdict
        )
        label = "SCAM" if fused_score >= 0.75 else "SUSPICIOUS" if fused_score >= 0.40 else "SAFE"
        print(f"\n[Scenario] {desc}:")
        print(f"  Inputs -> Transcript Risk: {t_risk}, Heuristics: {h_risk}, Advisories: {adv_count}")
        print(f"  Outputs -> Fused Risk Score: {fused_score:.2f}, Label: {label}")

    print("\n==================================================")
    print("             ALL TEST SCENARIOS COMPLETED          ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
