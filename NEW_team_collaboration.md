# Team Collaboration Plan — Phase 2: Live Call Guardian (Milestones 7–9)

This document coordinates the parallel development of the **Live Risk Score
(#5)**, **Escalation Coach (#7 reframed)**, and **Report Generator (#4)**
features for the 3-developer team. It follows the same working protocol as
`team_collaboration_plan (1).md` (Milestones 1–6) and the execution guardrails
in `.antigravityrules`. Full technical design lives in `NEW_ARCHITECTURE.md` —
read that first.

Milestone numbering continues from Phase 1 (which ended at Milestone 6).
**Every milestone must end with a fully runnable application** (guardrail from
`.antigravityrules`).

---

## 1. Developer Roles & System Boundaries

Ownership is divided so no two developers edit the same file within a milestone.

```
AI-Scam-Detection/
├── backend/
│   └── app/
│       ├── api/                      <-- Developer 1 (WS endpoint, report routes)
│       ├── models/schemas.py         <-- Developer 1 (owns ALL API/WS contracts)
│       ├── services/
│       │   ├── live_session.py       <-- Developer 2
│       │   ├── streaming_transcriber.py <-- Developer 2
│       │   ├── risk_engine.py        <-- Developer 2
│       │   ├── heuristic_scorer.py   <-- Developer 3
│       │   └── report_generator.py   <-- Developer 3
│       ├── database/                 <-- Developer 2
│       └── rag/                      <-- Developer 3
└── frontend/                         <-- Developer 1
```

| Developer | Domain | Key Files | Focus |
|---|---|---|---|
| **Developer 1** | Frontend & API surface | `frontend/`, `backend/app/api/`, `schemas.py` | WS client + endpoint, live UI (gauge, coach, report modal), contract schemas |
| **Developer 2** | Streaming core & persistence | `services/live_session.py`, `streaming_transcriber.py`, `risk_engine.py`, `database/` | Session orchestration, block-commit Whisper, Adaptive Risk Engine v2, DB extension |
| **Developer 3** | Intelligence layer | `services/heuristic_scorer.py`, `report_generator.py`, `rag/` | Heuristic scorer, incremental LLM audit prompt, question generation & response verdicts, complaint drafts |

**Contract-first rule:** Developer 1 commits the `LiveUpdate` / `ReportDraft`
Pydantic schemas and the WS message spec (NEW_ARCHITECTURE.md §4) **on day one
of Milestone 7**, before anyone writes logic. Devs 2 and 3 code against those
schemas. Any contract change requires a message in the team chat + a schema
commit *before* dependent code.

---

## 2. Milestone 7 — Live Streaming Skeleton

**Goal:** End-to-end live loop working: mic chunks stream over WS, transcript
grows on screen in near-real-time, and a *heuristic-only* risk score updates
every cycle. No LLM in the loop yet, no smoothing — prove the plumbing.

**Demo checkpoint:** speak a scam script near the mic; within ~10 s the
transcript appears and the raw score reacts.

### Developer 1: WS Client & Live Monitor UI
*   **Branch**: `feature/m7-live-ui`
*   **Tasks**:
    1. Commit `LiveUpdate` schema + WS protocol constants to `schemas.py` (contract-first rule).
    2. Create `backend/app/api/live.py`: `WS /api/v1/ws/live` — accept connection, parse `start`/binary/`end` frames, delegate to Dev 2's `LiveSession` (code against its interface; use a stub returning canned `LiveUpdate`s until merge).
    3. Create `LiveCallMonitor.jsx`: "Start/Stop Live Monitor" controls, optional caller-number input, `MediaRecorder.start(5000)` streaming each chunk over the WS as a binary frame.
    4. Add a "Live Monitor" tab to `Dashboard.jsx`; render the growing transcript (committed + partial styled differently) and the raw score as plain text for now.
*   **Antigravity Prompt**:
    > *"In the FastAPI backend create api/live.py with a WebSocket endpoint /api/v1/ws/live that accepts a JSON 'start' message, binary audio frames, and a JSON 'end' message, delegating to a LiveSession class (stub it). In React create LiveCallMonitor.jsx that opens the WebSocket, streams MediaRecorder chunks every 5 seconds as binary frames, and renders LiveUpdate JSON messages (transcript + risk) pushed by the server. Do not modify services/ or rag/."*

### Developer 2: Session Core & Streaming Transcriber
*   **Branch**: `feature/m7-stream-core`
*   **Tasks**:
    1. Create `live_session.py`: `LiveSession` class — holds session_id, cumulative audio buffer, committed/partial transcript, last scores; one `process_cycle()` method called per received chunk that returns a `LiveUpdate`.
    2. Create `streaming_transcriber.py` implementing the **block-commit strategy** (NEW_ARCHITECTURE.md §5): append bytes → decode full webm buffer to 16 kHz PCM numpy array → transcribe only the active ≤30 s block with faster-whisper tiny → commit block text when it exceeds 30 s.
    3. Reuse the existing thread-pool pattern from `whisper_service.py` so transcription never blocks the event loop.
    4. Call Dev 3's `HeuristicScorer.score(text)` for the cycle's raw risk (code against the interface; stub until merge).
*   **Antigravity Prompt**:
    > *"Create services/live_session.py and services/streaming_transcriber.py. LiveSession accumulates webm chunk bytes; StreamingTranscriber decodes the cumulative buffer to 16kHz mono PCM with PyAV/ffmpeg, transcribes only the audio after block_start with faster-whisper tiny in a threadpool, and commits the block text once the block exceeds 30 seconds. process_cycle() returns committed transcript, partial tail, and a raw risk from HeuristicScorer (stub). Do not modify api/ routes or react code."*

### Developer 3: Heuristic Scorer
*   **Branch**: `feature/m7-heuristics`
*   **Tasks**:
    1. Create `services/heuristic_scorer.py`: `HeuristicScorer.score(text) -> HeuristicResult` with tiered keyword rules (generalize the fallback logic already in `query_engine.py`):
       - Tier 3 (0.85+): OTP/PIN/CVV demands, "arrest", remote-app install (AnyDesk/TeamViewer), payment/transfer demands
       - Tier 2 (0.5–0.7): KYC/account-suspension, lottery/prize, police/CBI/customs identity claims
       - Tier 1 (0.2–0.4): urgency language, secrecy demands ("don't tell anyone")
    2. Include `trigger_llm: bool` in the result (True on any Tier 3 hit) — Milestone 8 uses it to fire an immediate LLM audit.
    3. Unit-test with scripts in `backend/scratch/test_heuristics.py` covering all three Phase 1 scam categories + a benign conversation.
    4. Begin drafting (not wiring) the incremental audit prompt for M8 per NEW_ARCHITECTURE.md §8.
*   **Antigravity Prompt**:
    > *"Create services/heuristic_scorer.py with a HeuristicScorer.score(text) static method returning a dataclass {risk: float, tier_hits: list[str], trigger_llm: bool}. Use three keyword tiers for Indian phone-scam patterns (OTP demands, arrest threats, remote app installs = highest). Add scratch tests. Do not modify api/, services/live_session.py, or react code."*

**Integration handshake (end of M7):** Dev 1 replaces the `LiveSession` stub
with Dev 2's real class; Dev 2 replaces the `HeuristicScorer` stub with Dev 3's.
Merge order: `m7-heuristics` → `m7-stream-core` → `m7-live-ui` → `main`.

---

## 3. Milestone 8 — Adaptive Risk Engine & Escalation Coach

**Goal:** The score behaves like accumulating evidence (smoothed, ratcheted,
with confidence), the LLM audits incrementally with the new JSON fields, and
the coach panel drives the MONITOR → VERIFY → DANGER flow — including the
question → response-verdict feedback loop.

**Demo checkpoint:** a staged scam call starts MONITOR, moves to VERIFY
(questions appear), the "scammer" refuses to answer, verdict comes back
EVASIVE, score ratchets into DANGER, defensive prompts + hang-up/report
guidance appear simultaneously.

### Developer 1: Gauge Animation & Coach Panel
*   **Branch**: `feature/m8-coach-ui`
*   **Tasks**:
    1. Upgrade `RiskGauge.jsx`: smooth needle animation toward `risk_smoothed`, uncertainty band whose width shrinks as `confidence` grows, mode-colored styling (MONITOR blue / VERIFY amber / DANGER red).
    2. Create `CoachPanel.jsx` rendering per mode: nothing extra (MONITOR); suggested verification questions as prominent cards (VERIFY); defensive prompts + "Hang up now" + pulsing Report button rendered **together** (DANGER).
    3. Show `red_flags` as a growing chips list; keep a small score-over-time sparkline from the update stream.
*   **Antigravity Prompt**:
    > *"Upgrade RiskGauge.jsx to animate toward risk_smoothed and render a confidence band. Create CoachPanel.jsx that switches on the mode field of LiveUpdate: VERIFY shows suggested_questions cards, DANGER shows safe_actions plus a Hang-up banner and highlighted Report button simultaneously. Do not modify backend services."*

### Developer 2: Risk Engine v2 (smoothing, ratchet, state machine)
*   **Branch**: `feature/m8-risk-v2`
*   **Tasks**:
    1. Extend `risk_engine.py` with `AdaptiveRiskEngine` (keep the existing static method for the batch path): EMA (α≈0.35), ratchet floor (`max(floor, 0.75 * peak_smoothed)`), confidence formula, per NEW_ARCHITECTURE.md §6.
    2. Implement the state machine with hysteresis (DANGER exits below 0.65 sustained 20 s; VERIFY exits below 0.35 sustained 15 s).
    3. Wire `LiveSession.process_cycle()`: blend heuristic + last LLM risk into `risk_raw`, run the engine, attach mode to the `LiveUpdate`.
    4. Implement the LLM throttle policy: call Dev 3's incremental audit at most every 20 s, immediately on `trigger_llm`, or when a question was suggested last audit and new speech arrived since.
    5. Apply the `question_response_verdict` adjustment (EVASIVE/REFUSED/THREATENED → +0.15–0.25 on risk_raw; PLAUSIBLE → −0.05).
*   **Antigravity Prompt**:
    > *"Extend risk_engine.py with an AdaptiveRiskEngine class holding per-session state: EMA smoothing alpha 0.35, a ratchet floor at 0.75 of peak, confidence from word count and audit count, and a MONITOR/VERIFY/DANGER state machine with hysteresis timers. Wire it into LiveSession.process_cycle with a 20-second LLM audit throttle that fires early on heuristic trigger_llm or pending question responses. Do not modify rag/ internals or react code."*

### Developer 3: Incremental LLM Audit & Question Loop
*   **Branch**: `feature/m8-llm-incremental`
*   **Tasks**:
    1. Add `RAGQueryEngine.evaluate_incremental(transcript, prior_questions: list[str])` producing the extended JSON: existing fields + `red_flags`, `suggested_questions`, `safe_actions`, `question_response_verdict` (NEW_ARCHITECTURE.md §8).
    2. System prompt must state: live, incomplete, *mixed two-speaker speakerphone* transcript with transcription noise — judge patterns, not verbatim wording.
    3. Question generation rules: only verification questions with a built-in exit (employee ID + "I'll call the official number back", written notice on official email, which branch/department). **Never** generate engagement-prolonging bait; cap at 3.
    4. Response-verdict logic: given `prior_questions` and the new transcript tail, classify the caller's reaction (EVASIVE / REFUSED / THREATENED / PLAUSIBLE / NOT_YET_ANSWERED).
    5. Extend the offline heuristic fallback so the whole loop demos without an API key (canned questions per scam category; verdict EVASIVE when refusal keywords appear).
*   **Antigravity Prompt**:
    > *"Add evaluate_incremental to rag/query_engine.py. It reuses ChromaDB retrieval, then prompts Qwen with the live partial transcript plus previously suggested questions, returning strict JSON with risk_score, scam_category, explanation, red_flags, suggested_questions (max 3, verification-only with an exit path), safe_actions, and question_response_verdict. Extend the offline fallback to cover all new fields. Do not modify services/ or react code."*

**Integration handshake (end of M8):** merge order `m8-llm-incremental` →
`m8-risk-v2` → `m8-coach-ui` → `main`. Joint test: the staged-call demo script
above, once with the OpenRouter key and once offline on fallbacks.

---

## 4. Milestone 9 — Report Generator & Persistence

**Goal:** Every finished live call is persisted with its score timeline; a
complaint draft is generated; the user can review, edit, copy, and send it via
the official channels. History shows past live sessions with sparklines.

**Demo checkpoint:** finish a staged call → ReportModal opens with a complete
pre-written complaint citing transcript quotes and RBI/CERT-In advisories →
edit → copy → mailto draft opens. The call appears in history with its
risk-over-time sparkline.

### Developer 1: Report UI & History Integration
*   **Branch**: `feature/m9-report-ui`
*   **Tasks**:
    1. Create `ReportModal.jsx`: editable textarea pre-filled from the draft, Copy button, `mailto:` link, and prominent links to cybercrime.gov.in, helpline 1930, DoT Chakshu, RBI Sachet. Clear text stating the user reviews and files it themselves.
    2. Create `backend/app/api/report.py`: `POST /api/v1/report/{log_id}` (generate/regenerate via Dev 3's generator) and `GET /api/v1/report/{log_id}`; add `ReportDraft` schema.
    3. Wire triggers: auto-open on session `final` message; Report button in DANGER mode; per-entry Report action in the history panel; render `score_timeline` sparklines in history.
*   **Antigravity Prompt**:
    > *"Create api/report.py with POST and GET /api/v1/report/{log_id} calling ReportGenerator (Dev 3). Create ReportModal.jsx with an editable pre-filled draft, copy-to-clipboard, a mailto: draft, and links to Indian official reporting channels. Open it automatically when the live session ends and from history entries. Do not modify services internals."*

### Developer 2: Session Finalize & DB Extension
*   **Branch**: `feature/m9-db-sessions`
*   **Tasks**:
    1. Extend `CallLog` with the new nullable columns (`session_id`, `caller_number`, `duration_s`, `peak_risk`, `score_timeline` JSON, `report_text`) per NEW_ARCHITECTURE.md §10; recreate `db.sqlite3` (no migration needed at this stage).
    2. Implement `LiveSession.finalize()`: assemble the final `AnalysisResponse`, persist via extended `crud.save_analysis_result`, record the score timeline sampled per cycle, return the `final` WS message with `log_id`.
    3. Add `crud.save_report_text(log_id, text)` + fetch helpers for the report endpoints and history.
    4. Ensure abrupt WS disconnects also finalize (client crash ≠ lost call data).
*   **Antigravity Prompt**:
    > *"Extend database/models.py CallLog with nullable columns session_id, caller_number, duration_s, peak_risk, score_timeline (JSON text), report_text. Implement LiveSession.finalize() persisting the completed live session including a per-cycle score timeline, also on abrupt disconnect. Add crud helpers to save and fetch report text. Do not modify api/ or react code."*

### Developer 3: Complaint Draft Generator
*   **Branch**: `feature/m9-report-llm`
*   **Tasks**:
    1. Create `services/report_generator.py`: `ReportGenerator.generate(call_log) -> str` prompting Qwen for a formal complaint: incident date/time, caller number if present, category, chronological summary, verbatim red-flag quotes, matched advisory citations (title + source), closing declaration.
    2. Template-based fallback (f-string skeleton filled from stored fields) when no API key — same offline-first pattern as the rest of the stack.
    3. Keep it factual: the prompt must forbid inventing details not present in the transcript/metadata (a fabricated complaint is worse than none).
    4. Scratch-test against Phase 1's three scam categories.
*   **Antigravity Prompt**:
    > *"Create services/report_generator.py with ReportGenerator.generate(call_log) that prompts Qwen via OpenRouter to write a formal cybercrime complaint draft strictly from the provided transcript, risk metadata, and advisories — instruct it to never invent facts. Include a no-API-key template fallback. Add scratch tests. Do not modify api/, database/, or react code."*

**Integration handshake (end of M9):** merge order `m9-report-llm` →
`m9-db-sessions` → `m9-report-ui` → `main`. Full-pipeline rehearsal of the
demo script end to end, offline and online.

---

## 5. Git Integration Protocol (unchanged from Phase 1)

1. **Sync local main** before merging: `git checkout main && git pull origin main`
2. **Merge main into your feature branch** and resolve conflicts locally: `git checkout feature/your-feature && git merge main`
3. Follow the per-milestone **merge order** listed above (intelligence layer → core → UI), since each later branch consumes the earlier one's interfaces.
4. Small, atomic commits with meaningful messages; commit to feature branches, never directly to `main` (per `.antigravityrules`).
5. **State Lock** (guardrail): stop at each milestone's demo checkpoint and verify as a team before starting the next milestone.

---

## 6. Definition of Done (per milestone)

- App runs end-to-end with `uvicorn` + `npm run dev`, **with and without** the OpenRouter API key (fallbacks must hold).
- The milestone's demo checkpoint passes on one machine using the phone-on-speaker setup.
- No developer has modified files outside their ownership boundary without a contract-change announcement.
- Scratch tests for new services pass.
- README/known-limitations updated if behaviour shown to users changed.
