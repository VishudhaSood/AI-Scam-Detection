# Project Target Architecture Flowchart

This document details the target architecture for the AI Scam Detection platform. Use this as the engineering blueprint for scaling the system.

---

## Target Flowchart Diagram

```text
                             User
                              │
                              ▼
                      React Frontend
                              │
                              ▼
                      POST /analyze
                              │
                              ▼
                         FastAPI
                              │
                    Request Validation
                              │
                    Audio Preprocessing
                              │
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
    Whisper STT                         Deepfake Detector
         │                                       │
         ▼                                       ▼
   Transcript                          AI Voice Score
         │
         ├──────────────────────┐
         ▼                      ▼
  Qwen Classifier         BGE Embeddings
         │                      │
         ▼                      ▼
 Scam Category          Embedding Vector
         │                      │
         └──────────────┬───────┘
                        ▼
                  ChromaDB Search
        (RBI + CERT + Scam Calls)
                        │
                        ▼
               Retrieved Documents
                        │
                        ▼
               Qwen Reasoning
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
  Explanation                  Confidence
                        │
                        ▼
                  Risk Engine
        (Voice + LLM + Rules)
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
 PostgreSQL                    React Dashboard
```

---

## Component Details

### 1. Ingestion & Validation
*   **React Frontend**: Records audio natively from the microphone or handles call recording file uploads.
*   **FastAPI / analyze**: Validates requests via Pydantic and formats data.

### 2. Audio Processing (Parallel Branches)
*   **Whisper STT**: Transcribes call voice waveforms locally using `faster-whisper` to output text.
*   **Deepfake Detector**: Extracts vocal frequency signatures to calculate biometric cloning probabilities.

### 3. Dual RAG Index & Classifiers
*   **Qwen Classifier**: Runs an initial LLM query to label the call type.
*   **BGE Embeddings**: Translates transcript text into vector dimensions for ChromaDB searches.
*   **ChromaDB Search**: Performs cosine-similarity lookups on RBI and CERT-In advisories.

### 4. Risk Fusion & Storage
*   **Risk Engine**: Fuses the biometric voice clone rating and semantic transcript threat levels.
*   **PostgreSQL**: Serves as the central logging database (backed up by SQLite for local developer builds).
