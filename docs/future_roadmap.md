# AI Scam Detection - Future Roadmap & Scaling

This document logs architectural improvements and future features to implement as the platform scales beyond the initial hackathon prototype.

---

## 1. Phase 4: Production PDF Ingestion Pipeline
*   **Goal**: Replace the manually summarized advisory text files in `knowledge_base/` with raw official PDF alerts directly downloaded from the Reserve Bank of India (RBI) and CERT-In websites.
*   **Implementation Steps**:
    1.  Install `pypdf` or `pdfplumber` in the Python virtual environment:
        ```bash
        pip install pypdf
        ```
    2.  Update the indexing script [index_docs.py](file:///c:/Users/vishu/OneDrive/Desktop/Vishudha/Study%20material/Project/AI_Scammer/AI-Scam-Detection/AI-Scam-Detection/backend/app/rag/index_docs.py) with a PDF text extractor:
        ```python
        from pypdf import PdfReader
        
        def extract_text_from_pdf(pdf_path):
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        ```
    3.  Implement a semantic splitter (e.g., recursive character chunking by paragraphs) to slice raw PDF text before embedding it.
    4.  Save official source URLs inside the database metadata so users click directly to the official government PDF warnings.

---

## 2. Additional Future Enhancements
*   **Database Migrations**: Switch SQLite to PostgreSQL for multi-user dashboard analytics.
*   **User Alerts**: Add SMS / Email integrations to alert family members when a high-risk scam call is audited.
