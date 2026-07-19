import sys
import os
import json

# Setup Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.rag.query_engine import RAGQueryEngine

def run_test_suite():
    print("==================================================")
    print("Milestone 8 - Incremental LLM Audit Test Runner")
    print("==================================================")

    # 1. Step 1: Start of Call (Scammer initiates KYC suspension bait)
    transcript_step_1 = (
        "Hello, I am calling from SBI main office card division. "
        "Your account is currently suspended due to incomplete KYC update details. "
        "You must complete the verification process immediately."
    )
    
    print("\n[Step 1] Sending initial suspicious KYC prompt...")
    res_1 = RAGQueryEngine.evaluate_incremental(transcript_step_1, prior_questions=[])
    
    print(f"Risk Score   : {res_1.get('risk_score')}")
    print(f"Label        : {res_1.get('label')}")
    print(f"Explanation  : {res_1.get('explanation')}")
    print(f"Questions    : {res_1.get('suggested_questions')}")
    print(f"Verdict      : {res_1.get('question_response_verdict')}")
    
    assert res_1.get("label") in ["SUSPICIOUS", "SCAM"]
    assert len(res_1.get("suggested_questions", [])) > 0
    
    # Capture the suggested questions to feed into Step 2
    prior_questions = res_1.get("suggested_questions", [])

    # 2. Step 2: Scam escalation (User asks suggested questions, scammer gets hostile)
    # Append user question and scammer's angry evasion to transcript
    transcript_step_2 = (
        transcript_step_1 + 
        f" User asked: {prior_questions[0] if prior_questions else 'What is your employee ID?'}"
        " Caller replied: No! Why are you asking me that? Do not ask questions, just tell me the OTP "
        "or your bank account will be blocked forever within 1 hour!"
    )
    
    print("\n[Step 2] Sending follow-up transcript with scammer's hostile refusal...")
    res_2 = RAGQueryEngine.evaluate_incremental(transcript_step_2, prior_questions=prior_questions)
    
    print(f"Risk Score   : {res_2.get('risk_score')}")
    print(f"Label        : {res_2.get('label')}")
    print(f"Explanation  : {res_2.get('explanation')}")
    print(f"Safe Actions : {res_2.get('safe_actions')}")
    print(f"Verdict      : {res_2.get('question_response_verdict')}")
    
    assert res_2.get("question_response_verdict") in ["EVASIVE", "REFUSED", "THREATENED"]
    assert res_2.get("label") == "SCAM"
    assert len(res_2.get("safe_actions", [])) > 0

    print("\n==================================================")
    print("ALL INCREMENTAL LLM AUDIT TEST SCENARIOS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_test_suite()
