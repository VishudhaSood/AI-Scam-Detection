import os
import chromadb
from chromadb.utils import embedding_functions

# Path configuration: Resolve to backend/chroma_db
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROMA_DB_DIR = os.path.join(BACKEND_DIR, "chroma_db")

class VectorStoreManager:
    """
    Handles local ChromaDB vector database connections and collections.
    Uses a thread-safe singleton pattern for client initialization.
    """
    _client = None
    _collection = None

    @classmethod
    def get_client(cls) -> chromadb.PersistentClient:
        if cls._client is None:
            # PersistentClient automatically stores database folders on disk
            cls._client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        return cls._client

    @classmethod
    def get_collection(cls) -> chromadb.Collection:
        if cls._collection is None:
            client = cls.get_client()
            # ONNXMiniLM_L6_V2 runs sentence-transformers models on local CPU via ONNX.
            # Downloads the lightweight 'all-MiniLM-L6-v2' (120MB) once to ~/.cache/chroma.
            embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
            
            cls._collection = client.get_or_create_collection(
                name="scam_advisories",
                embedding_function=embedding_fn,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity for semantic matching
            )
        return cls._collection
