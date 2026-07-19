import sys
import os
import json

# Setup Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.heuristic_scorer import HeuristicScorer
from app.rag.query_engine import RAGQueryEngine

def interactive_test_loop():
    print("==================================================")
    # Highlight the test tool in alignment with Developer 3 rules
    print("AI Scam Guardian - Intelligence Layer Tester CLI")
    print("==================================================")
    print("This utility tests:")
    print("1. HeuristicScorer (Tiers 1, 2, 3)")
    print("2. ChromaDB RAG (Advisories retrieval)")
    print("3. RAGQueryEngine.evaluate_incremental (Live Qwen LLM / Fallback)")
    print("==================================================")

    # Allow toggling API key to test the "Loud Fallback"
    test_mode = "LIVE AI"
    original_key = os.environ.get("OPENROUTER_API_KEY", "")
    
    prior_questions = []

    while True:
        print(f"\n[Mode: {test_mode}] | Stored Questions: {len(prior_questions)}")
        print("Commands:")
        print("  /toggle  - Toggle between Live AI and Offline Fallback Mock")
        print("  /clear   - Clear conversation history / prior questions")
        print("  /quit    - Exit the tester")
        print("Or type a sentence/transcript segment below and press Enter:")
        
        user_input = input("> ").strip()
        if not user_input:
            continue

        if user_input.lower() == "/quit":
            break
        elif user_input.lower() == "/toggle":
            if test_mode == "LIVE AI":
                test_mode = "OFFLINE FALLBACK MOCK"
                os.environ["OPENROUTER_API_KEY"] = "invalid_key_for_testing"
                print(">>> Switched to OFFLINE mode. OpenRouter calls will fail and run Mock Fallbacks.")
            else:
                test_mode = "LIVE AI"
                os.environ["OPENROUTER_API_KEY"] = original_key
                print(">>> Switched to LIVE AI mode. Calls will use openrouter/free.")
            continue
        elif user_input.lower() == "/clear":
            prior_questions = []
            print(">>> Conversation history cleared.")
            continue

        print("\n--- Running Audits ---")

        # 1. Test Heuristics Scorer
        heur_res = HeuristicScorer.score(user_input)
        print(f"[Heuristic Scorer]")
        print(f"  Raw Score  : {heur_res.risk}")
        print(f"  Tier Hits  : {heur_res.tier_hits}")
        print(f"  Trigger LLM: {heur_res.trigger_llm}")

        # 2. Test ChromaDB RAG Vector Store
        print(f"\n[ChromaDB RAG Retrieval]")
        try:
            from app.rag.vector_store import VectorStoreManager
            col = VectorStoreManager.get_collection()
            raw_res = col.query(query_texts=[user_input], n_results=1)
            raw_dist = raw_res.get("distances", [[]])[0][0] if "distances" in raw_res and raw_res["distances"] else 9.9
            print(f"  ChromaDB Raw Distance: {raw_dist:.3f}")
            
            advisories = RAGQueryEngine.query_advisories(user_input, n_results=1)
            if advisories:
                print(f"  Matched Title : {advisories[0].title} [{advisories[0].source}]")
                print(f"  Description Snippet: {advisories[0].description[:100]}...")
            else:
                print("  No matching advisories found (filtered out by distance threshold > 1.25).")
        except Exception as e:
            print(f"  Error querying vector database: {e}")

        # 3. Test LLM Audit Loop (Qwen / Fallback)
        print(f"\n[Incremental LLM Audit]")
        try:
            audit = RAGQueryEngine.evaluate_incremental(user_input, prior_questions)
            
            # Print formatted results
            print(f"  Risk Score : {audit.get('risk_score')}")
            print(f"  Verdict    : {audit.get('label')}")
            print(f"  Category   : {audit.get('scam_category')}")
            print(f"  Explanation: {audit.get('explanation')}")
            print(f"  Questions  : {audit.get('suggested_questions')}")
            print(f"  Safe Advice: {audit.get('safe_actions')}")
            print(f"  Q-Verdict  : {audit.get('question_response_verdict')}")
            
            # Accumulate suggested questions for the next turn
            new_questions = audit.get("suggested_questions", [])
            if new_questions:
                prior_questions = list(set(prior_questions + new_questions))

        except Exception as e:
            print(f"  Critical error during LLM audit: {e}")

if __name__ == "__main__":
    interactive_test_loop()
