import sys
import os

# Append the backend directory to Python path so we can import services
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.heuristic_scorer import HeuristicScorer

def test_heuristic_pipeline():
    print("==================================================")
    print("Testing Milestone 7 - Heuristic Scorer")
    print("==================================================")

    # Scenario 1: Bank KYC Suspension (OTP requested -> Tier 3 hit)
    test_1 = "Hello, SBI manager here. Your card is blocked. Tell me the OTP immediately to verify."
    res_1 = HeuristicScorer.score(test_1)
    print(f"\n1. KYC Suspension OTP test:\n   Text: '{test_1}'")
    print(f"   Risk Score: {res_1.risk} (Expected: >=0.85)")
    print(f"   Hits      : {res_1.tier_hits}")
    print(f"   Trigger   : {res_1.trigger_llm} (Expected: True)")
    assert res_1.risk >= 0.85
    assert res_1.trigger_llm is True
    print("   [SUCCESS] Scenario 1 Passed!")

    # Scenario 2: Lottery prize draw (Tier 2 hits + Tier 1 urgency -> Tier 2 result)
    test_2 = "Congratulations, you won a KBC lucky draw prize of 25 Lakhs! Please confirm now."
    res_2 = HeuristicScorer.score(test_2)
    print(f"\n2. KBC Lottery test:\n   Text: '{test_2}'")
    print(f"   Risk Score: {res_2.risk} (Expected: 0.50 - 0.74)")
    print(f"   Hits      : {res_2.tier_hits}")
    print(f"   Trigger   : {res_2.trigger_llm} (Expected: False)")
    assert 0.50 <= res_2.risk <= 0.74
    assert res_2.trigger_llm is False
    print("   [SUCCESS] Scenario 2 Passed!")

    # Scenario 3: Mumbai Customs / Arrest threat (Arrest -> Tier 3 hit)
    test_3 = "This is customs. An illegal package was sent in your name. We are issuing an arrest warrant."
    res_3 = HeuristicScorer.score(test_3)
    print(f"\n3. Customs Arrest Warrant test:\n   Text: '{test_3}'")
    print(f"   Risk Score: {res_3.risk} (Expected: >=0.85)")
    print(f"   Hits      : {res_3.tier_hits}")
    print(f"   Trigger   : {res_3.trigger_llm} (Expected: True)")
    assert res_3.risk >= 0.85
    assert res_3.trigger_llm is True
    print("   [SUCCESS] Scenario 3 Passed!")

    # Scenario 4: Secrecy Urgency Chat (Urgency only -> Tier 1 result)
    test_4 = "Please do this immediately. This is emergency, keep it secret."
    res_4 = HeuristicScorer.score(test_4)
    print(f"\n4. Secrecy Urgency test:\n   Text: '{test_4}'")
    print(f"   Risk Score: {res_4.risk} (Expected: 0.20 - 0.49)")
    print(f"   Hits      : {res_4.tier_hits}")
    print(f"   Trigger   : {res_4.trigger_llm} (Expected: False)")
    assert 0.20 <= res_4.risk <= 0.49
    assert res_4.trigger_llm is False
    print("   [SUCCESS] Scenario 4 Passed!")

    # Scenario 5: Benign Conversation (Safe)
    test_5 = "Hi, are you free for dinner tonight? Let me know when you get this."
    res_5 = HeuristicScorer.score(test_5)
    print(f"\n5. Safe Benign Conversation test:\n   Text: '{test_5}'")
    print(f"   Risk Score: {res_5.risk} (Expected: 0.05)")
    print(f"   Hits      : {res_5.tier_hits}")
    print(f"   Trigger   : {res_5.trigger_llm} (Expected: False)")
    assert res_5.risk == 0.05
    assert res_5.trigger_llm is False
    print("   [SUCCESS] Scenario 5 Passed!")

    print("\n==================================================")
    print("ALL HEURISTIC SCORER SCENARIOS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    test_heuristic_pipeline()
