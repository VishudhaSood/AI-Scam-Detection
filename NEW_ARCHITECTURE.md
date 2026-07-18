# NEW ARCHITECTURE — Live Call Guardian (Phase 2)

> Supersedes the batch-only pipeline described in `.antigravityrules` (System
> Architecture Map) for the live-monitoring path. The existing
> `POST /api/v1/analyze` batch endpoint **stays untouched** for file uploads and
> pasted transcripts — Phase 2 adds a parallel streaming path alongside it.

---

## 1. Scope of Phase 2 (what we decided to build)

From `Improvements.md`, we are implementing:

| # | Feature | Decision |
|---|---------|----------|
| **#5** | Risk score that rises/falls live as the call progresses | Build, via **speakerphone-to-desktop** capture (live cellular tap is impossible for third-party apps — see Improvements.md §0) |
| **#7** | Escalation coach (reframed) | Build as a **two-stage state machine**: at *medium* risk, suggest identity-verification questions whose answers feed back into the score; at *high* risk, show defensive prompts **and** hang-up/report guidance simultaneously |
| **#4** | Report button with pre-written complaint draft | Build, **human-in-the-loop** (user reviews/edits/sends — we never auto-file) |

**Explicitly out of scope this phase:** native mobile app, unknown-number
interception (#3), speaker diarization (#6), real deepfake model (stays mocked
and labeled as such).

---

## 2. The capture model (how live audio actually reaches us)

```
   Scammer ──cellular──> User's phone (SPEAKERPHONE ON)
                              │
                              ~ sound through the air ~
                              │
                         Desktop microphone
                              │
                    React app (MediaRecorder)
```

The user starts a "Live Call Monitor" session in the desktop web app, puts the
phone call on speaker next to the laptop. The browser mic hears **both sides**
of the conversation. This is the only capture path available to a third-party
app and it works with our existing `getUserMedia` code.

**Consequences to design around:**
- Audio quality is degraded (room acoustics, phone speaker) → use Whisper
  beam_size tuned down, accept imperfect transcripts, weight heuristics on
  keywords not exact phrasing.
- We cannot tell speakers apart — the transcript is one merged stream. The LLM
  prompt must be written to evaluate a *mixed two-party conversation*.
- Consent: the user is a party to the call. Document the consent-law caveat in
  the README; do not present the tool as covert recording.

---

## 3. Updated System Architecture Map

```
Phone call (speakerphone) ~~acoustic~~> Desktop Mic
  └── React LiveCallMonitor  (MediaRecorder, start(5000) → 5s chunks)
        └── WS /api/v1/ws/live   (binary audio frames + JSON control msgs)
              └── FastAPI LiveSession  (per-call in-memory state, keyed by session_id)
                    │
                    ├── StreamingTranscriber
                    │     ├── append chunk bytes → cumulative webm buffer
                    │     ├── decode full buffer → 16 kHz mono PCM (cheap)
                    │     └── faster-whisper (tiny) on ACTIVE 30s BLOCK only
                    │           └── committed transcript + live partial tail
                    │
                    ├── Fast Heuristic Scorer        (every chunk, zero cost)
                    │     └── tiered keyword/urgency rules → raw_risk hint
                    │
                    ├── Incremental LLM Audit        (throttled: ~20s OR trigger)
                    │     ├── ChromaDB advisory retrieval (existing RAG)
                    │     └── Qwen via OpenRouter → strict JSON:
                    │           { risk_score, scam_category, red_flags[],
                    │             suggested_questions[], safe_actions[],
                    │             question_response_verdict }
                    │
                    └── Adaptive Risk Engine v2
                          ├── EMA smoothing + ratchet floor + confidence
                          └── State machine: MONITOR / VERIFY / DANGER
                                └── WS push → animated gauge + coach panel

End of call ("end" msg or WS close)
  └── Session finalizer
        ├── Report Generator (Qwen) → formal complaint draft
        ├── SQLite persist (CallLog + score timeline + report text)
        └── ReportModal (edit / copy / mailto / portal links)
```

---

## 4. WebSocket protocol (`WS /api/v1/ws/live`)

The contract between Dev 1 (client) and Dev 2 (server). Binary frames carry
audio; JSON text frames carry control and updates.

**Client → Server**
```json
{ "type": "start", "caller_number": "optional user-entered string" }
```
- binary frames: raw MediaRecorder webm chunks (5s timeslice, single stream —
  chunks after the first are continuations, so server-side byte-append yields a
  valid file)
```json
{ "type": "end" }
```

**Server → Client** (pushed after each processing cycle, ~every 5s)
```json
{
  "type": "update",
  "session_id": "uuid",
  "elapsed_s": 45,
  "transcript_committed": "…finalized text…",
  "transcript_partial": "…live tail, may still change…",
  "risk_raw": 0.58,
  "risk_smoothed": 0.51,
  "confidence": 0.55,
  "label": "SUSPICIOUS",
  "mode": "VERIFY",
  "scam_category": "Bank Impersonation (KYC)",
  "red_flags": ["Caller demanded OTP", "Urgency pressure"],
  "suggested_questions": ["Ask for their employee ID and branch name…"],
  "safe_actions": [],
  "advisories": [ { "title": "…", "source": "RBI", "description": "…" } ]
}
```
```json
{ "type": "final", "session_id": "uuid", "report_id": 12, "…full AnalysisResponse fields…": "…" }
```

**Design rule:** `suggested_questions` is only non-empty in `VERIFY` mode;
`safe_actions` is only non-empty in `DANGER` mode. The UI renders whatever the
server sends — all mode logic lives server-side (single source of truth).

---

## 5. Streaming transcription design (the block-commit strategy)

Whisper is not a streaming model, so we fake it with bounded re-transcription:

1. Server appends every binary chunk to the session's cumulative webm buffer.
2. Each cycle, decode the **full** buffer to a 16 kHz mono float32 numpy array
   (decoding is ~100× faster than transcription — this is cheap).
3. Maintain a pointer `block_start`. Each cycle, transcribe only
   `pcm[block_start : now]` — the **active block** — and treat its text as the
   *partial* (mutable) transcript tail.
4. When the active block exceeds **30 s**: append its text to the *committed*
   transcript, set `block_start = now`. Transcription cost per cycle is
   therefore bounded at ≤30 s of audio regardless of call length.

Trade-off: a word can be clipped at each 30 s block boundary. Acceptable — the
risk analysis works on keywords and patterns, not verbatim accuracy.

---

## 6. Adaptive Risk Engine v2 (feature #5)

Extends the existing `RiskEngine` (`backend/app/services/risk_engine.py`).
A raw per-cycle score that jumps around looks broken; the displayed score must
**accumulate evidence**. Three mechanisms:

**a) Blended raw score per cycle**
```
risk_raw = max(heuristic_score, last_llm_risk)      # cheap signal every 5s,
                                                    # LLM signal every ~20s
```

**b) EMA smoothing + ratchet floor**
```
smoothed  = α * risk_raw + (1 - α) * smoothed_prev        (α ≈ 0.35)
floor     = max(floor_prev, 0.75 * peak_smoothed)          # ratchet: strong
smoothed  = max(smoothed, floor)                           # evidence doesn't
                                                           # un-happen
```
The score can drift down slowly if the call turns benign, but a confirmed red
flag (e.g., OTP demand) permanently raises the floor. No flicker, no
"scam → safe → scam" bouncing on the gauge.

**c) Confidence (how much evidence we have)**
```
confidence = min(1.0, words_heard / 120) * min(1.0, llm_audits_done / 2)
```
The UI renders low confidence as a **wide uncertainty band** around the gauge
needle early in the call, narrowing as evidence accumulates. This prevents the
demo-killing failure of a confident wrong score in the first 10 seconds.

**State machine (drives the coach, feature #7):**

| Mode | Condition (on `smoothed`) | UI behaviour |
|------|---------------------------|--------------|
| `MONITOR` | < 0.40 | Passive: gauge + live transcript only |
| `VERIFY`  | 0.40 – 0.74 | Coach shows 2–3 **verification questions** |
| `DANGER`  | ≥ 0.75 | Coach shows **defensive prompts + hang-up/report guidance simultaneously**; Report button pulses |

**Hysteresis:** dropping out of `DANGER` requires `smoothed < 0.65` sustained
for 20 s; dropping out of `VERIFY` requires `< 0.35` sustained for 15 s. Modes
must feel stable, not twitchy.

---

## 7. The Escalation Coach loop (feature #7, reframed)

This is the core novelty: **active probing that feeds the score**, followed by
defense — never open-ended scambaiting.

```
                 ┌─────────────────────────────────────────────┐
                 │  VERIFY mode (medium risk)                  │
                 │                                             │
  transcript ──> │  LLM generates 2–3 identity-proof questions │
                 │  tailored to the claimed persona, e.g.:     │
                 │   • "Ask for their employee ID and which    │
                 │      branch they sit in."                   │
                 │   • "Say you will call back on the bank's   │
                 │      official number — ask which department │
                 │      to request."                           │
                 │   • "Ask them to send the notice in writing │
                 │      from their official email."            │
                 └──────────────────┬──────────────────────────┘
                                    │ user asks; scammer answers
                                    │ (heard via speakerphone)
                                    ▼
                 ┌─────────────────────────────────────────────┐
                 │  Response analysis (next LLM audit cycle)   │
                 │  Prompt includes the questions that were    │
                 │  suggested. LLM returns a                   │
                 │  question_response_verdict:                 │
                 │   • EVASIVE / REFUSED / THREATENED          │
                 │       → risk_raw += 0.15–0.25 (score rises) │
                 │   • PLAUSIBLE / VERIFIABLE detail given     │
                 │       → mild negative adjustment            │
                 │   • NOT_YET_ANSWERED → no change            │
                 └──────────────────┬──────────────────────────┘
                                    │ score crosses 0.75
                                    ▼
                 ┌─────────────────────────────────────────────┐
                 │  DANGER mode (high risk) — simultaneous:    │
                 │   • Defensive prompts: "Do NOT share OTP",  │
                 │     "Do NOT install any app", "Do not pay"  │
                 │   • Exit guidance: "Hang up now" +          │
                 │     Report button (feature #4) highlighted  │
                 └─────────────────────────────────────────────┘
```

**Safety rails (non-negotiable):**
- Questions are only ever *verification* questions with a built-in exit ("I'll
  call the official number back") — never bait to prolong the call.
- The moment `DANGER` triggers, question suggestions stop and hang-up guidance
  takes over. The tool's goal is a *shorter* scam call with better evidence,
  not a longer one.
- A "Hang up now" recommendation is always one tap away in every mode.

**Why an evasion-detection loop is defensible:** the question set is what any
bank/police body already tells citizens to ask; we are automating the advice,
and the *scammer's refusal to answer* is itself high-quality evidence that
raises the score — which is exactly the user's stated intent for #7.

---

## 8. Incremental LLM audit (prompt contract change)

`RAGQueryEngine` (`backend/app/rag/query_engine.py`) gains an incremental mode.
Differences from the batch prompt:

- Input: committed + partial transcript so far, **plus** the list of
  verification questions previously suggested (if any).
- The system prompt states the text is a *live, possibly incomplete, mixed
  two-speaker conversation captured via speakerphone* — expect transcription
  noise, judge on patterns.
- Output JSON gains four fields on top of the existing ones:
  `red_flags` (string[]), `suggested_questions` (string[], only meaningful for
  medium risk), `safe_actions` (string[]), `question_response_verdict`
  (`EVASIVE | REFUSED | THREATENED | PLAUSIBLE | NOT_YET_ANSWERED | N/A`).

**Throttling policy (cost control):** audit at most every ~20 s, but fire
immediately when (a) the heuristic scorer hits a high-tier keyword (OTP,
"arrest", remote-app install, payment demand), or (b) a verification question
was suggested last cycle and new speech has arrived (analyze the answer
promptly). The heuristic fallback in `query_engine.py` already gives us free
per-chunk scoring between audits.

---

## 9. Report Generator (feature #4)

**Trigger:** automatic draft on session finalize; also a `Report` button in the
UI usable at any time and from history.

**Backend:** new `backend/app/services/report_generator.py` + new router
`backend/app/api/report.py`:
- `POST /api/v1/report/{log_id}` → generates (or regenerates) the draft
- `GET  /api/v1/report/{log_id}` → fetches stored draft

The generator prompts Qwen with the full transcript + risk metadata + matched
advisories to produce a **formal complaint draft**: incident date/time,
caller number (if user entered it), scam category, chronological summary,
verbatim red-flag quotes from the transcript, matched RBI/CERT-In advisory
citations, and a closing declaration line. Falls back to a template-based
draft (no LLM) when the API key is absent — same pattern as the existing
heuristic fallback.

**Frontend `ReportModal.jsx`:** editable textarea pre-filled with the draft +
**Copy** button + `mailto:` draft + prominent links to the official channels
(National Cyber Crime Reporting Portal cybercrime.gov.in, helpline 1930, DoT
Chakshu, RBI Sachet). **The user reviews and submits — we never auto-file.**

---

## 10. Database changes (SQLite, `CallLog` extension)

New columns on `CallLog` (`backend/app/database/models.py`):

| Column | Type | Purpose |
|--------|------|---------|
| `session_id` | TEXT nullable | Links live sessions to their log |
| `caller_number` | TEXT nullable | User-entered, goes into the report |
| `duration_s` | INTEGER nullable | Call length |
| `peak_risk` | FLOAT nullable | Highest smoothed score reached |
| `score_timeline` | TEXT (JSON) nullable | `[{t, risk_smoothed, mode}, …]` for the history sparkline |
| `report_text` | TEXT nullable | The generated complaint draft |

All nullable → old rows and the batch `POST /analyze` path keep working. For
the hackathon, recreate `db.sqlite3` rather than writing a migration.

---

## 11. File-by-file change map

**New files**
| File | Owner | Responsibility |
|------|-------|----------------|
| `backend/app/api/live.py` | Dev 1 | WebSocket endpoint, connection lifecycle, msg routing |
| `backend/app/services/live_session.py` | Dev 2 | Per-call session state, orchestration of transcriber → scorer → engine per cycle |
| `backend/app/services/streaming_transcriber.py` | Dev 2 | Chunk buffer, PCM decode, block-commit Whisper strategy (§5) |
| `backend/app/services/heuristic_scorer.py` | Dev 3 | Tiered keyword/urgency scorer, trigger flags for LLM audit |
| `backend/app/services/report_generator.py` | Dev 3 | Complaint draft (LLM + template fallback) |
| `backend/app/api/report.py` | Dev 1 | Report REST endpoints |
| `frontend/src/components/LiveCallMonitor.jsx` | Dev 1 | Session start/stop, MediaRecorder streaming, WS client |
| `frontend/src/components/CoachPanel.jsx` | Dev 1 | MONITOR/VERIFY/DANGER coach UI |
| `frontend/src/components/ReportModal.jsx` | Dev 1 | Editable draft, copy/mailto/portal links |

**Modified files**
| File | Owner | Change |
|------|-------|--------|
| `backend/app/services/risk_engine.py` | Dev 2 | Add v2: EMA, ratchet, confidence, state machine + hysteresis (§6) |
| `backend/app/rag/query_engine.py` | Dev 3 | Incremental audit mode + new JSON fields + throttle triggers (§8) |
| `backend/app/models/schemas.py` | Dev 1 | `LiveUpdate`, `ReportDraft` schemas (contract owner) |
| `backend/app/database/models.py`, `crud.py` | Dev 2 | New columns + save-on-finalize (§10) |
| `backend/app/main.py` | Dev 1 | Mount live + report routers |
| `frontend/src/components/RiskGauge.jsx` | Dev 1 | Animated needle + confidence band |
| `frontend/src/components/Dashboard.jsx` | Dev 1 | Third tab: "Live Monitor" |

---

## 12. Known limitations (state these honestly in the demo)

1. Deepfake probability remains **mocked** in live mode (real streaming
   anti-spoofing is a separate research-grade workstream).
2. Speakerphone capture degrades transcription quality; scoring is designed
   around keywords/patterns to tolerate this.
3. No speaker separation — the LLM judges the merged conversation.
4. Report filing is manual by design (no public filing APIs; human-in-the-loop
   is both a legal necessity and a feature).
5. Call-recording consent law varies by jurisdiction; the user is a party to
   the call, and the README must carry this caveat.
