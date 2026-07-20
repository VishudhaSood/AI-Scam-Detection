import os
import sys

# Ensure the backend directory is in the Python path for app imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.rag.vector_store import VectorStoreManager

# Resolve paths
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "knowledge_base")

def get_official_url(source: str) -> str:
    """
    Maps the advisory source name to its official portal URL across 30+ major Indian banks.
    """
    src_lower = source.lower()
    if "sbi" in src_lower or "state bank of india" in src_lower:
        return "https://bank.sbi"
    elif "hdfc" in src_lower:
        return "https://www.hdfcbank.com"
    elif "icici" in src_lower:
        return "https://www.icicibank.com"
    elif "axis" in src_lower:
        return "https://www.axisbank.com"
    elif "kotak" in src_lower:
        return "https://www.kotak.com"
    elif "indusind" in src_lower:
        return "https://www.indusind.com"
    elif "yes bank" in src_lower:
        return "https://www.yesbank.in"
    elif "idfc" in src_lower:
        return "https://www.idfcfirstbank.com"
    elif "canara" in src_lower:
        return "https://canarabank.com"
    elif "union bank" in src_lower:
        return "https://www.unionbankofindia.co.in"
    elif "bank of india" in src_lower or "boi" in src_lower:
        return "https://bankofindia.co.in"
    elif "baroda" in src_lower:
        return "https://www.bankofbaroda.in"
    elif "pnb" in src_lower or "punjab national bank" in src_lower:
        return "https://www.pnbindia.in"
    elif "federal" in src_lower:
        return "https://www.federalbank.co.in"
    elif "bandhan" in src_lower:
        return "https://bandhanbank.com"
    elif "idbi" in src_lower:
        return "https://www.idbibank.in"
    elif "maharashtra" in src_lower:
        return "https://bankofmaharashtra.in"
    elif "punjab & sind" in src_lower or "punjab and sind" in src_lower:
        return "https://punjabandsindbank.co.in"
    elif "uco bank" in src_lower:
        return "https://www.ucobank.com"
    elif "indian overseas bank" in src_lower or "iob" in src_lower:
        return "https://www.iob.in"
    elif "indian bank" in src_lower:
        return "https://www.indianbank.in"
    elif "central bank" in src_lower:
        return "https://www.centralbankofindia.co.in"
    elif "rbl" in src_lower:
        return "https://www.rblbank.com"
    elif "south indian" in src_lower:
        return "https://www.southindianbank.com"
    elif "karur vysya" in src_lower or "kvb" in src_lower:
        return "https://www.kvb.co.in"
    elif "city union" in src_lower:
        return "https://www.cityunionbank.com"
    elif "karnataka bank" in src_lower:
        return "https://karnatakabank.com"
    elif "tamilnad mercantile" in src_lower or "tmb" in src_lower:
        return "https://www.tmb.in"
    elif "india post" in src_lower or "ippb" in src_lower:
        return "https://www.ippbonline.com"
    elif "au small" in src_lower or "au bank" in src_lower:
        return "https://www.aubank.in"
    elif "rbi" in src_lower or "reserve bank" in src_lower:
        return "https://www.rbi.org.in"
    else:
        return "https://www.cert-in.org.in"

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
            url = get_official_url(source)
            
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
    Reads files from the knowledge base, computes vector embeddings, and indexes them into ChromaDB / Fallback store.
    """
    print("Initializing Vector DB collection...")
    collection = VectorStoreManager.get_collection()
    
    # Files to parse
    files_to_index = ["rbi_advisories.txt", "cert_advisories.txt", "bank_advisories.txt"]
    all_advisories = []
    
    for filename in files_to_index:
        filepath = os.path.join(KB_DIR, filename)
        print(f"Parsing {filename}...")
        parsed = parse_advisories(filepath)
        all_advisories.extend(parsed)
        
    if not all_advisories:
        print("No documents found to index.")
        return
        
    print(f"Loaded {len(all_advisories)} advisories across RBI, CERT-In, and major banks. Upserting to Vector DB...")
    
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
