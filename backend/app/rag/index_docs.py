import os
import sys

# Ensure the backend directory is in the Python path for app imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.rag.vector_store import VectorStoreManager

# Resolve paths
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "knowledge_base")

def parse_advisories(file_path: str):
    """
    Parses a seed advisory text file.
    Blocks are separated by double newlines. Inside each block:
    TITLE: ...
    SOURCE: ...
    CONTENT: ...
    """
    if not os.path.exists(file_path):
        print(f"Warning: File {file_path} not found.")
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")
    parsed_items = []

    for block in blocks:
        lines = block.strip().split("\n")
        title, source, text_content = "", "", ""
        
        for line in lines:
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("SOURCE:"):
                source = line.replace("SOURCE:", "").strip()
            elif line.startswith("CONTENT:"):
                text_content = line.replace("CONTENT:", "").strip()
        
        if title and source and text_content:
            # Map standard URLs based on source
            url = "https://www.rbi.org.in" if "rbi" in source.lower() else "https://www.cert-in.org.in"
            
            parsed_items.append({
                "title": title,
                "source": source,
                "description": text_content,
                "url": url,
                "document": f"Title: {title}\nSource: {source}\nDescription: {text_content}"
            })
            
    return parsed_items

def index_all_documents():
    """
    Reads files from the knowledge base, computes vector embeddings, and indexes them into ChromaDB.
    """
    print("Initializing ChromaDB collection...")
    collection = VectorStoreManager.get_collection()
    
    # Files to parse
    files_to_index = ["rbi_advisories.txt", "cert_advisories.txt"]
    all_advisories = []
    
    for filename in files_to_index:
        filepath = os.path.join(KB_DIR, filename)
        print(f"Parsing {filename}...")
        parsed = parse_advisories(filepath)
        all_advisories.extend(parsed)
        
    if not all_advisories:
        print("No documents found to index.")
        return
        
    print(f"Loaded {len(all_advisories)} advisories. Upserting to ChromaDB...")
    
    # Prepare packages for ChromaDB ingestion
    documents = []
    metadatas = []
    ids = []
    
    for i, adv in enumerate(all_advisories):
        # We index the combined document string to ensure rich semantic keyword matches
        documents.append(adv["document"])
        
        # Save standard metadata that matches our API Advisory schema contract
        metadatas.append({
            "title": adv["title"],
            "source": adv["source"],
            "description": adv["description"],
            "url": adv["url"]
        })
        
        ids.append(f"advisory_{i}")
        
    # Bulk insert
    collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    print("Indexing completed successfully!")
    print(f"Stored {collection.count()} vectors in collection '{collection.name}'.")

if __name__ == "__main__":
    index_all_documents()
