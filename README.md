# 🛡️ AI Scam Guard Platform

> **Real-Time AI Fraud Evaluation & Live Speakerphone Guardian**
> An intelligent, real-time scam detection and caller verification system designed to protect citizens from financial fraud, impersonation, and "Digital Arrest" coercion calls.

---

## 📌 Project Overview

The **AI Scam Guard Platform** is a real-time call monitoring and scam detection engine. By putting incoming calls on speakerphone or auditing transcripts/recordings, the platform continuously analyzes spoken dialogue for social engineering tactics, urgency pressure, identity fraud, and regulatory warning matches.

It combines **Real-time Web Speech Transcription**, **Groq Llama-3.3 LLM Reasoning**, **Semantic RAG Advisory Retrieval**, **Negation-Aware Keyword Scanners**, and a **Multi-Factor Evidence Fusion Engine** to provide immediate, actionable threat intelligence and defensive coaching to the user.

---

## ✨ Key Features

### 🎙️ 1. Speakerphone Live Guardian
- **Real-Time Monitoring**: Monitors calls via browser-native Web Speech API or local Whisper STT.
- **Incremental Threat Evaluation**: Evaluates risk continuously in ~5-second streaming cycles.
- **Adaptive Coaching Modes**: Transitions between **MONITOR** (Safe), **VERIFY** (Suggests exit questions), and **DANGER** (Shows immediate defensive actions).
- **Interactive Reaction Feedback**: One-tap feedback buttons (*"🛑 Caller Refused / Evasive"* & *"🤬 Caller Became Hostile"*) allow instant manual risk escalation during live verification.

### 🧠 2. Multilingual LLM Reasoning & Hinglish Guardrails
- **Powered by Groq API**: High-speed, low-latency evaluation using `llama-3.3-70b-versatile`.
- **Hinglish Scam Scanner**: Detects mixed Hindi-English scam pressure phrases (*"paisa transfer karo"*, *"khata block ho jayega"*, *"police aayegi"*, *"giraftari warrant"*, *"penalty bharna padega"*).
- **Negation & Context Awareness**: Intelligent context understanding prevents false alarms. Protective advice (e.g., *"do not share your OTP"* or *"never give your password"*) is correctly recognized as **SAFE**.

### 📄 3. Interactive Cybercrime Complaint Generator & Audit Trail
- **Multi-Portal Reporting Links**: Direct quick links to **Helpline 1930** ([cybercrime.gov.in](https://cybercrime.gov.in)), **DoT Chakshu** ([sancharsaathi.gov.in/sachet](https://sancharsaathi.gov.in/sachet)), and **RBI Sachet Fraud Portal** ([sachet.rbi.org.in](https://sachet.rbi.org.in)).
- **Interactive Complaint Editor Modal (`ReportModal.jsx`)**: Pop-up modal with an editable complaint text body, form inputs for victim details (Complainant Name, Impersonated Bank, Financial Loss Amount ₹, Transaction UTR Ref #), copy to clipboard, and official `.txt` report download.
- **Mid-Call Complaint Shortcut**: A prominent **"🚨 Prepare Cybercrime Complaint Now"** shortcut button inside the **DANGER** live coaching banner allows users to prepare and edit complaint drafts mid-call without waiting to end the session.
- **Fact-Constrained LLM Summaries**: Powered by `ReportGenerator` service using Groq to write formal 2-sentence executive summaries bounded strictly by verified threat telemetry.
- **Real-Time SHA-256 Legal Audit Hash**: Client-side Web Crypto API (`crypto.subtle.digest`) re-computes a 64-character SHA-256 cryptographic audit hash in real time as text is edited, stamping a tamper-proof `DIGITAL INTEGRITY & AUDIT TRAIL` signature at the bottom of the complaint file.

### 📚 4. RAG Regulatory & Banking Knowledge Base
- **45 Official Advisories Indexed**: Comprehensive corpus covering RBI, CERT-In, MHA, SEBI, IRDAI, EPFO, FIU-IND, RERA, and **30+ major Indian Public, Private, Small Finance, & Payments Banks**.
- **Comprehensive Financial Scam Coverage**: Specialized detection for Stock Market / Mutual Fund tip scams, Crypto exchange lockup frauds, Insurance bonus claims, Provident Fund withdrawal assistance fees, Matrimonial NRI romance extortion, Travel/Hotel booking phishing, Digital Arrest, YONO APK malware, DISCOM electricity bill scams, SIM Swap / eSIM fraud, UPI QR code receive-money tricks, and credit card reward point cash-in fraud.
- **Zero-Crash Architecture**: Uses a pure-Python fallback vector store (`FallbackCollection`) to ensure 100% reliable performance on Windows without native C++ ONNX DLL crashes.

### 📊 5. Multi-Factor Evidence Fusion Engine
Combines 4 independent signal dimensions with mathematical floor guarantees:
- **Transcript LLM Analysis**: `45%`
- **Scam Heuristics Scanner**: `25%`
- **RAG Advisory Match**: `20%`
- **Verification Question Verdict**: `10%`

### 📜 6. Session Audit History
- **Saved Call History Modal**: One-click **"📜 Past Audits"** drawer fetches past saved call scans from `db.sqlite3` via `/api/v1/analyze/history`.
- **Persistent Storage**: Database files and vector indexes are preserved across server restarts.

---

## 🏗️ System Architecture

```text
               ┌──────────────────────────────────────────────┐
               │         React + Vite Dashboard               │
               │ (Live Monitor / Audio / Direct Transcript)   │
               └──────────────────────┬───────────────────────┘
                                      │
                         WebSocket / HTTP API
                                      │
               ┌──────────────────────▼───────────────────────┐
               │           FastAPI Backend                    │
               │        (app/api/live.py & analyze.py)        │
               └──────────────────────┬───────────────────────┘
                                      │
               ┌──────────────────────▼───────────────────────┐
               │         Evidence Orchestrator                │
               └─┬──────────────┬──────────────┬──────────────┴─┐
                 │              │              │                │
┌────────────────▼─┐  ┌─────────▼──────┐ ┌─────▼──────────┐ ┌───▼────────────┐
│ Whisper / Speech │  │ Heuristic      │ │ RAG Vector     │ │ Verification   │
│ Reasoning (Groq) │  │ Scorer         │ │ Store (Chroma) │ │ Response Engine│
└──────────────────┘  └────────────────┘ └────────────────┘ └────────────────┘
                 │              │              │                │
                 └──────────────┴──────┬───────┴────────────────┘
                                       │
                        ┌──────────────▼──────────────┐
                        │   Evidence Fusion Engine    │
                        │   & Adaptive Risk Engine    │
                        └─────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** installed and added to `PATH`
- **Node.js 18+** & `npm` installed
- **Groq API Key**: Get a free API key from [Groq Console](https://console.groq.com/)

---

### Setup Instructions

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/VishudhaSood/AI-Scam-Detection.git
   cd AI-Scam-Detection
   ```

2. **Configure Environment Variables**:
   Navigate to the `backend` folder, create a `.env` file (or copy from `.env.example`), and insert your Groq API key:
   ```env
   GROQ_API_KEY=gsk_your_actual_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   USE_FALLBACK_DB=true
   ```

3. **Install Dependencies**:
   - **Backend Dependencies**:
     ```bash
     cd backend
     python -m venv venv
     venv\Scripts\activate
     pip install -r requirements.txt
     cd ..
     ```
   - **Frontend Dependencies**:
     ```bash
     cd frontend
     npm install
     cd ..
     ```

---

## ⚡ Quick Launch (Windows One-Click)

Simply double-click **`run_app.bat`** (or run `.\run_app.bat` in terminal):

```cmd
run_app.bat
```

The script will automatically:
1. Detect and activate the Python virtual environment (`backend\venv`).
2. Seed the RAG vector store with official regulatory advisories if not already indexed.
3. Start the FastAPI backend server on `http://127.0.0.1:8000`.
4. Start the React Vite frontend server on `http://localhost:5173`.
5. Launch your default browser to `http://localhost:5173`.

---

## 🧪 Verification & Test Suite

The project includes an automated test harness with 20 labeled evaluation scenarios covering negation detection, Digital Arrest threats, lottery scams, tech support fraud, and benign small talk.

To run the test suite:
```bash
cd backend
venv\Scripts\python.exe scratch\eval_transcripts.py
```

Expected output:
```text
======================================================================
  Results: 20/20 passed  (0 failed)
  Pass rate: 100%
======================================================================

  CRITICAL: 'hi do not give me otp' -> SAFE  [PASSED]
```

---

## 📁 Repository Structure

```text
AI-Scam-Detection/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI REST & WebSocket endpoint routers
│   │   ├── database/        # SQLite CallLog models & CRUD handlers
│   │   ├── models/          # Pydantic schemas & data contracts
│   │   ├── rag/             # ChromaDB vector store & Groq RAG engine
│   │   └── services/        # Evidence Orchestrator, Heuristic Scorer, Risk Engine
│   ├── .env                 # API Keys (git-ignored)
│   ├── .env.example         # Template for environment configuration
│   ├── requirements.txt     # Backend Python packages
│   └── run.py               # FastAPI server entry point
├── frontend/
│   ├── src/
│   │   ├── components/      # React components (LiveCallMonitor, CoachPanel, RiskGauge)
│   │   ├── App.jsx          # Main application layout
│   │   └── main.jsx         # Vite entry point
│   └── package.json         # Frontend Node dependencies
├── knowledge_base/          # Seed regulatory advisory documents (RBI, CERT-In, MHA)
├── run_app.bat              # One-click launch script
└── README.md                # Project documentation
```

---

## 👥 Contributors

- **Pranava Swarup**
- **Vishudha Sood**
- **Yash Sultania**