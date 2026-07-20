"""
Eval Harness — 20+ labeled test cases to verify the AI scam detection system.
Tests negation awareness, Digital Arrest detection, and benign call handling.

Usage:
    cd backend
    python scratch/eval_transcripts.py

Requires: GROQ_API_KEY in backend/.env (or will use keyword fallback).
"""
import os
import sys
import json

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.rag.query_engine import RAGQueryEngine

# ── Test cases: (transcript, expected_label, description) ──
# expected_label: "SAFE", "SUSPICIOUS", or "SCAM"
TEST_CASES = [
    # === SAFE — Benign / Negation / Warning ===
    ("hi do not give me otp", "SAFE", "Negation: speaker warning against OTP sharing"),
    ("never share your OTP with anyone", "SAFE", "Safety warning about OTP"),
    ("my bank called me back and everything is fine", "SAFE", "Benign post-call statement"),
    ("hello how are you doing today", "SAFE", "Plain small talk"),
    ("I refuse to give you my password, stop asking", "SAFE", "Speaker refusing to share credentials"),
    ("don't tell anyone your bank PIN number, it's private", "SAFE", "Protective advice about PIN"),
    ("good morning, the weather is nice today", "SAFE", "Completely benign conversation"),
    ("I called my bank and they confirmed no issues with my account", "SAFE", "Benign confirmation"),

    # === SUSPICIOUS — Scam signals present but not extreme ===
    ("sir your KYC has expired, you need to update it immediately or your account will be blocked", "SUSPICIOUS", "KYC update pressure"),
    ("congratulations you have won a lucky draw of 50 lakh rupees", "SUSPICIOUS", "Lottery prize announcement"),
    ("this is customs department, a parcel in your name has been intercepted", "SUSPICIOUS", "Customs impersonation opening"),

    # === SCAM — Clear scam demands ===
    ("I am calling from CBI. There is a warrant against you. Transfer 5 lakh to this account immediately or you will be arrested", "SCAM", "Digital Arrest: CBI impersonation with money demand"),
    ("you are under digital arrest. Do not disconnect this call. Transfer the settlement fee now", "SCAM", "Digital Arrest: explicit digital arrest threat"),
    ("this is cyber police. Your Aadhaar has been used for money laundering. You must pay 2 lakh security deposit right now", "SCAM", "Digital Arrest: cyber police with Aadhaar threat"),
    ("your card has been blocked. Give me your OTP right now to unblock it", "SCAM", "Bank impersonation demanding OTP"),
    ("you won KBC lottery of 25 lakh. Please pay processing fee of 5000 rupees", "SCAM", "Lottery scam with fee demand"),
    ("download AnyDesk and give me the access code. Your computer has been hacked", "SCAM", "Tech support scam with remote access demand"),
    ("I am inspector Sharma from narcotics bureau. We found contraband in a FedEx package registered to your name. Pay settlement fee or face arrest", "SCAM", "Digital Arrest: narcotics + FedEx variant"),
    ("sir your account will be suspended in 1 hour. Share your CVV and PIN to verify", "SCAM", "Bank impersonation with CVV/PIN demand"),
    ("transfer money to this account right now or the police will come to your house", "SCAM", "Direct money transfer threat"),
]


def run_eval():
    print("=" * 70)
    print("  AI Scam Detection — Evaluation Harness")
    print("=" * 70)
    print()

    passed = 0
    failed = 0
    results = []

    for i, (transcript, expected, description) in enumerate(TEST_CASES, 1):
        try:
            result = RAGQueryEngine.evaluate_transcript(transcript)
            actual_label = result.get("label", "UNKNOWN")
            risk_score = result.get("risk_score", 0.0)
            explanation = result.get("explanation", "")[:100]

            # Check pass/fail
            # For safety: SAFE expected = only SAFE passes
            # For scam detection: if expected is SCAM, both SCAM and SUSPICIOUS pass
            # (catching it at all is good; SUSPICIOUS is acceptable)
            if expected == "SAFE":
                is_pass = actual_label == "SAFE"
            elif expected == "SCAM":
                is_pass = actual_label in ["SCAM", "SUSPICIOUS"]
            elif expected == "SUSPICIOUS":
                is_pass = actual_label in ["SUSPICIOUS", "SCAM"]
            else:
                is_pass = actual_label == expected

            status = "[PASS]" if is_pass else "[FAIL]"
            if is_pass:
                passed += 1
            else:
                failed += 1

            print(f"  [{i:2d}] {status}  expected={expected:11s}  got={actual_label:11s}  risk={risk_score:.2f}")
            print(f"       {description}")
            print(f"       \"{transcript[:60]}{'...' if len(transcript)>60 else ''}\"")
            print()

            results.append({
                "test": i,
                "transcript": transcript,
                "expected": expected,
                "actual": actual_label,
                "risk": risk_score,
                "pass": is_pass,
                "description": description,
            })
        except Exception as e:
            failed += 1
            print(f"  [{i:2d}] [ERROR] {e}")
            print(f"       {description}")
            print()

    # Summary
    total = passed + failed
    print("=" * 70)
    print(f"  Results: {passed}/{total} passed  ({failed} failed)")
    print(f"  Pass rate: {passed/total*100:.0f}%")
    print("=" * 70)

    # Check if the critical negation test passed
    if results and results[0]["pass"]:
        print("\n  CRITICAL: 'hi do not give me otp' -> SAFE  [PASSED]")
    else:
        print("\n  CRITICAL: 'hi do not give me otp' -> STILL FAILING  [FAILED]")

    return results


if __name__ == "__main__":
    run_eval()
