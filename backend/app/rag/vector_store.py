import os
import json
import hashlib
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction

# Path configuration: Resolve to backend/chroma_db
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROMA_DB_DIR = os.path.join(BACKEND_DIR, "chroma_db")

class HashEmbeddingFunction(EmbeddingFunction):
    """
    A pure-Python fallback embedding function that creates 384-dimensional
    normalized bag-of-words vectors using the hashing trick.
    Requires no external native libraries (like onnxruntime).
    """
    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for doc in input:
            words = doc.lower().split()
            vec = [0.0] * 384
            if words:
                for w in words:
                    # Use md5 to hash the word into one of the 384 bins
                    h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
                    vec[h % 384] += 1.0
                # Normalize vector to unit length for cosine similarity
                norm = sum(x*x for x in vec) ** 0.5
                if norm > 0:
                    vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings

class FallbackCollection:
    """
    A pure-Python, zero-dependency alternative to ChromaDB collection.
    Saves documents to a JSON file and uses Jaccard keyword similarity search.
    Guarantees 100% stability on systems with DLL/C++ compilation issues.
    """
    def __init__(self, name="scam_advisories"):
        self.name = name
        self.db_path = os.path.join(CHROMA_DB_DIR, "fallback_db.json")
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = []
        else:
            self.data = []

    def _save(self):
        os.makedirs(CHROMA_DB_DIR, exist_ok=True)
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving fallback database: {e}")

    def count(self) -> int:
        return len(self.data)

    def upsert(self, documents, metadatas, ids):
        id_map = {item["id"]: item for item in self.data}
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            item = {"id": doc_id, "document": doc, "metadata": meta}
            id_map[doc_id] = item
        self.data = list(id_map.values())
        self._save()

    # Filler words that would otherwise dominate the word-overlap score and
    # make benign small talk "match" advisories through shared stopwords.
    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "if", "then", "is", "are", "was",
        "were", "be", "been", "to", "of", "in", "on", "at", "for", "from",
        "with", "by", "as", "it", "its", "this", "that", "these", "those",
        "i", "you", "he", "she", "we", "they", "your", "my", "his", "her",
        "our", "their", "me", "him", "them", "us", "do", "does", "did", "not",
        "no", "yes", "have", "has", "had", "will", "would", "can", "could",
        "should", "shall", "may", "might", "there", "here", "what", "which",
        "who", "how", "when", "where", "why", "all", "any", "so", "just",
        "please", "now", "today", "very", "am", "pm", "up", "out", "about"
    }

    @classmethod
    def _meaningful_words(cls, text: str) -> set:
        words = set()
        for raw in text.lower().split():
            w = raw.strip('.,!?;:"()[]')
            if w and w not in cls.STOPWORDS:
                words.add(w)
        return words

    def query(self, query_texts, n_results=2):
        if not query_texts or not self.data:
            return {"metadatas": [[]], "distances": [[]]}

        query_words = self._meaningful_words(query_texts[0])

        scored_items = []
        for item in self.data:
            doc_words = self._meaningful_words(item["document"])
            intersection = query_words.intersection(doc_words)
            union = query_words.union(doc_words)
            score = len(intersection) / len(union) if union else 0.0
            # One shared meaningful word is noise, not a topical match
            if len(intersection) >= 2:
                scored_items.append((score, item["metadata"]))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        top = scored_items[:n_results]
        # Report distances (1 - similarity) so upstream threshold checks see
        # real values instead of defaulting to a perfect 0.0 match.
        return {
            "metadatas": [[meta for _, meta in top]],
            "distances": [[round(1.0 - score, 4) for score, _ in top]],
        }

class VectorStoreManager:
    """
    Handles local ChromaDB vector database connections and collections.
    Bypasses to FallbackCollection if USE_FALLBACK_DB=true or load fails.
    """
    _client = None
    _collection = None
    _use_fallback = True  # Default to pure-Python FallbackCollection to prevent Windows C++ DLL crashes

    @classmethod
    def get_client(cls):
        if os.environ.get("USE_FALLBACK_DB") == "true" or cls._use_fallback:
            return None
        if cls._client is None:
            try:
                import chromadb
                cls._client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
            except BaseException:
                cls._use_fallback = True
                return None
        return cls._client

    @classmethod
    def get_collection(cls):
        # 1. Force fallback if requested by environment or if fallback active
        if os.environ.get("USE_FALLBACK_DB") == "true" or cls._use_fallback:
            if cls._collection is None or not isinstance(cls._collection, FallbackCollection):
                print("Initializing pure-Python FallbackCollection (zero-dependency vector store).")
                cls._collection = FallbackCollection()
            return cls._collection

        if cls._collection is None:
            try:
                import chromadb
                client = cls.get_client()
                if client is None:
                    cls._use_fallback = True
                    return cls.get_collection()
                
                embedding_fn = HashEmbeddingFunction()
                cls._collection = client.get_or_create_collection(
                    name="scam_advisories",
                    embedding_function=embedding_fn,
                    metadata={"hnsw:space": "cosine"}
                )
            except BaseException as e:
                print(f"ChromaDB native client failed ({e}). Swapping to pure-Python FallbackCollection.")
                cls._use_fallback = True
                cls._collection = FallbackCollection()
                
        return cls._collection
