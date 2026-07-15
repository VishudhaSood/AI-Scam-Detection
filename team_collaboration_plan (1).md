# Team Collaboration Plan: Milestones 2 & 3

This document coordinates the parallel development of **Milestone 2 (Audio & Speech Pipeline)** and **Milestone 3 (RAG Knowledge Base & LLM Analysis)** for a 3-developer team using Antigravity and Git.

---

## 1. Developer Roles & System Boundaries

To eliminate merge conflicts, the codebase is divided so each developer owns distinct directories and responsibilities.

```
AI-Scam-Detection/
├── backend/
│   └── app/
│       ├── api/          <-- Developer 1 (Web Interface & API Routing) 
│       ├── models/       <-- Developer 1 & 2 (Pydantic & Database schemas)
│       ├── services/     <-- Developer 2 (Whisper & Deepfake logic)
│       ├── database/     <-- Developer 2 (SQL Persistence)
│       └── rag/          <-- Developer 3 (Vector database & LLM processing)
└── frontend/             <-- Developer 1 (React UI / Audio Capture)
```

| Developer | Domain | Key Files / Folders | Focus |
| :--- | :--- | :--- | :--- |
| **Developer 1** | Frontend & Web APIs | `frontend/`, `backend/app/api/` | UI/UX, Audio recording/capturing, Web endpoints, CORS, request/response validation contracts. |
| **Developer 2** | Audio & Persistence | `backend/app/services/`, `backend/app/database/` | Whisper Speech-to-Text integration, Deepfake synthetic voice scoring, SQLite database logs. |
| **Developer 3** | RAG & Cognitive LLM | `backend/app/rag/`, `knowledge_base/` | Document chunking, ChromaDB vector indexing, OpenAI Embeddings, GPT prompt auditing. |

---

## 2. Milestone 2: Audio & Speech Pipeline

**Goal**: React captures microphone audio -> sends file to FastAPI -> Whisper transcribes to text -> Service runs Deepfake check -> API returns text & voice clone safety metrics.

### Developer 1: Audio Recorder & Router
*   **Branch**: `feature/m2-ui-capture`
*   **Tasks**:
    1. Update the React `Dashboard.jsx` to request microphone permissions using the browser's **MediaRecorder API**.
    2. Add a visual "Record / Stop" button with recording duration counters.
    3. Update the `POST /api/v1/analyze` router to accept an uploaded file.
    4. Import and call Developer 2's Whisper (`transcribe_audio`) and Deepfake (`detect_deepfake`) service functions.
*   **Antigravity Prompt**:
    > *"Implement browser MediaRecorder inside Dashboard.jsx to record audio in webm/wav format. Expose a record button. In the FastAPI backend analyze.py, import and call WhisperService.transcribe_audio(file) and WhisperService.detect_deepfake(file) which Developer 2 will write. Ensure we handle FastAPI's UploadFile object."*

### Developer 2: Whisper & Deepfake Engines
*   **Branch**: `feature/m2-audio-services`
*   **Tasks**:
    1. Create a service file `backend/app/services/whisper_service.py`.
    2. Write `transcribe_audio(file: UploadFile)` to accept a FastAPI UploadFile, extract the audio bytes (or save to temporary location), and transcribe using a local library (faster-whisper) or OpenAI Whisper API.
    3. Write `detect_deepfake(file: UploadFile)` (accepts FastAPI UploadFile, computes pitch/spectrogram metrics or returns mock synthetic probability between 0.0 and 1.0).
    4. Create `backend/app/services/risk_engine.py` containing `RiskEngine.calculate_combined_risk(deepfake_prob, llm_risk_score)` to calculate the final `risk_score` and return the classification `label` (SAFE, SUSPICIOUS, SCAM).
*   **Antigravity Prompt**:
    > *"Create a new file whisper_service.py in backend/app/services/. Write a WhisperService class with static methods: transcribe_audio(file: UploadFile) which returns a transcript string, and detect_deepfake(file: UploadFile) which returns a float probability of synthetic voice cloning. Also create risk_engine.py to compute the combined risk score and label. Do not modify api/ routes or react code."*

### Developer 3: Knowledge Base RAG Setup
*   **Branch**: `feature/m2-rag-init`
*   **Tasks**:
    1. Create the `knowledge_base/` root folder. Populate it with markdown/PDF files of RBI advisories, CERT-In threat reports, and known scam conversation transcripts.
    2. Create `backend/app/rag/vector_store.py` to initialize the ChromaDB client.
    3. Write an offline script to read the knowledge base files, compute embeddings (using `sentence-transformers` or OpenAI Embeddings), and index them into ChromaDB.
*   **Antigravity Prompt**:
    > *"Create rag/vector_store.py under backend/app/. Set up ChromaDB local persistent client. Write an indexing function that chunks text files in a local knowledge_base/ directory, converts them into vector embeddings, and saves them to ChromaDB. Ensure this indexing only runs once and is not generated during query time."*

---

## 3. Milestone 3: RAG Retrieval & LLM Analysis

**Goal**: Ingest transcript text -> query ChromaDB vector store -> extract relevant RBI warnings -> bundle them into an LLM prompt -> GPT evaluates risk score + returns an explanation -> save evaluation log in SQLite.

### Developer 1: Multi-Model Evaluation Dashboard
*   **Branch**: `feature/m3-dashboard-logs`
*   **Tasks**:
    1. Build a history drawer/sidebar in the React UI displaying previous call evaluations (fetched from the database).
    2. Update dashboard components to handle and format structural JSON explanations with nested source references returned by Developer 3's LLM engine.
*   **Antigravity Prompt**:
    > *"Update React UI to fetch a list of previous scan audits from a GET /api/v1/history endpoint. Display them in a history panel. Format the output layout to render multi-model explanation details cleanly."*

### Developer 2: Database Persistence
*   **Branch**: `feature/m3-database-logs`
*   **Tasks**:
    1. Define the SQL database models (e.g., using `SQLAlchemy` or `SQLModel`) in `backend/app/database/models.py`.
    2. Define `CallLog` model with columns matching the API contract: `id`, `transcript`, `risk_score`, `label`, `scam_category`, `deepfake_probability`, `explanation`, and `analyzed_at`.
    3. Create database tables on startup.
    4. Expose save and query methods in `backend/app/database/crud.py` (e.g. `save_analysis_result()`, `get_analysis_history()`).
*   **Antigravity Prompt**:
    > *"Setup SQLAlchemy in backend/app/database/ with a local SQLite file db.sqlite3. Create a CallLog model containing transcript, risk_score, label, scam_category, deepfake_probability, explanation, and analyzed_at fields. Expose CRUD functions to save logs and read history."*

### Developer 3: Retrieval-Augmented Generation & Prompt Auditor
*   **Branch**: `feature/m3-rag-llm`
*   **Tasks**:
    1. In `backend/app/rag/query_engine.py`, write a query function that converts the transcript to an embedding, searches ChromaDB for the top 2-3 most similar advisories, and formats them.
    2. Write an evaluation function that calls GPT (via `openai` package) using a system prompt that looks like:
       *"Evaluate this conversation. Use these advisories as context. Output a JSON format: risk_score (0-1), category, explanation, matched advisory indices."*
*   **Antigravity Prompt**:
    > *"Implement query_engine.py under backend/app/rag/. Write a query function to retrieve the top 3 matches from ChromaDB based on similarity. Write a prompt builder that passes this retrieved context and the call transcript to GPT-4 to return an explanation, risk score, and category. Output strict JSON."*

---

## 4. Git Integration Protocol

To merge code cleanly at the end of each milestone:

1.  **Sync Local Main**: Always update your local `main` branch before merging:
    ```bash
    git checkout main
    git pull origin main
    ```
2.  **Rebase/Merge Main into your Feature Branch**:
    ```bash
    git checkout feature/your-feature
    git merge main
    ```
    *Solve any minor conflicts in your IDE before proceeding.*
3.  **Deploy Integration Handshakes**: During integration, import the actual services and combine them. For example, Developer 1 replaces the mock analysis in `analyze.py` with calls to all services:
    ```python
    # backend/app/api/analyze.py
    from app.services.whisper_service import WhisperService
    from app.services.risk_engine import RiskEngine
    from app.rag.query_engine import RAGQueryEngine
    from app.database import crud
    
    # 1. Transcribe audio & check for deepfakes
    transcript = await WhisperService.transcribe_audio(file)
    deepfake_prob = await WhisperService.detect_deepfake(file)
    
    # 2. Run LLM audit & RAG lookup on transcript
    rag_result = RAGQueryEngine.evaluate(transcript)
    
    # 3. Calculate final combined risk and classification label via Risk Engine
    final_risk, label = RiskEngine.calculate_combined_risk(deepfake_prob, rag_result.risk_score)
    
    # 4. Construct final analysis response
    response_data = AnalysisResponse(
        transcript=transcript,
        risk_score=final_risk,
        label=label,
        scam_category=rag_result.category,
        deepfake_probability=deepfake_prob,
        explanation=rag_result.explanation,
        advisories=rag_result.advisories
    )
    
    # 5. Persist the log in Database
    crud.save_analysis_result(response_data)
    
    return response_data
    ```
