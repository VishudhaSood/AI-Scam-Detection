import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.index_docs import index_all_documents

if __name__ == "__main__":
    try:
        index_all_documents()
        print("SUCCESS")
    except Exception as e:
        print(f"EXCEPTION OCCURRED: {e}")
        traceback.print_exc()
