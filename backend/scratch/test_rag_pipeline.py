import os
import sys

# Ensure backend directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.query_engine import RAGQueryEngine

def run_test():
    print("==================================================")
    print("Testing Developer 3 RAG & Qwen Pipeline")
    print("==================================================")

    # Test 1: ChromaDB Semantic Search
    test_query = "This is a call about KBC lottery winnings of 25 lakhs. Please deposit transfer taxes."
    print(f"\n1. Testing Advisory Retrieval for query:\n   '{test_query}'")
    advisories = RAGQueryEngine.query_advisories(test_query, n_results=2)
    
    if not advisories:
        print("[FAIL] No advisories returned. Make sure index_docs.py completed successfully.")
    else:
        print(f"[SUCCESS] Retrieved {len(advisories)} matching advisories:")
        for idx, adv in enumerate(advisories):
            print(f"   [{idx+1}] Source: {adv.source} | Title: {adv.title}")
            print(f"       Desc: {adv.description[:100]}...")

    # Test 2: Full LLM Scam Audit
    print(f"\n2. Testing Qwen Scam Audit for query:\n   '{test_query}'")
    
    # Check if API Key is configured
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key or "your_openrouter" in api_key:
        print("[WARNING] OPENROUTER_API_KEY is not set in .env. Running fallback mock test.")
    else:
        print(f"[API] Found OpenRouter API Key. Querying model: {os.environ.get('OPENROUTER_MODEL', 'qwen/qwen-2.5-72b-instruct')}")

    try:
        evaluation = RAGQueryEngine.evaluate_transcript(test_query)
        print("\n[SUCCESS] Audit Completed Successfully!")
        print(f"   Risk Score : {evaluation.get('risk_score')}")
        print(f"   Label      : {evaluation.get('label')}")
        print(f"   Category   : {evaluation.get('scam_category')}")
        print(f"   Explanation: {evaluation.get('explanation')}")
        print(f"   Advisories : {len(evaluation.get('advisories', []))} attached.")
    except Exception as e:
        print(f"[ERROR] Error during evaluation: {e}")

if __name__ == "__main__":
    run_test()
