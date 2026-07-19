# Flaws & Improvements — Post-M8 Integration Sweep

**Date:** 2026-07-19 · **Branch:** `feature/m7-live-ui` · **Author:** Dev 1
**Scope:** Everything found while integrating Dev 2 (evidence orchestrator / AASIST)
and Dev 3 (LLM audit hardening) and fixing the post-merge regressions. Items are
ordered by how much they threaten the demo. The AI/semantic-understanding problem
has its own deep-dive: see `LLM_RAG_FIX_PLAN.md`.

---

## 1. Fixed on this branch (for the record)

| Fix | Commit |
|---|---|
| M8 coach UI (mode banner, questions, safe actions, red flags) + timer drift correction | `be5aabd` |
| Merge conflict resolution: coach panel + evidence breakdown + reasoning trace coexist | `4ab900e` |
| Batch `/analyze` 500s (undefined `content` in text path; TempSession missing `risk_engine`) | `66cc378` |
| Live Whisper flooding (client now batches 5s PCM frames instead of 4 frames/sec) | `66cc378` |
| `0xDF` deepfake-frame tag could false-match raw PCM (1/256 chance, ate 5s of audio) — now requires EBML header | `66cc378` |
| Malformed binary frame killed the whole live session — now logged and dropped | `66cc378` |
| DANGER guidance flicker — sticky guidance + persistent EVASIVE/REFUSED/THREATENED verdict | `66cc378` |
| RAG matched advisories on benign/empty speech — fallback DB returned **no distances**, so the 1.25 filter was a no-op; now stopword-filtered Jaccard + ≥2 shared meaningful words | `66cc378` |
| Reasoning trace claimed "Qwen LLM analyzed" when the offline fallback answered — now surfaces the audit's own `[FALLBACK MOCK ...]` explanation | `66cc378` |
| Whisper transcript stall at ~30–40s (whole active block re-transcribed per cycle; commit threshold halved to 15s) | `9d97c25` |
| Voice-clone scan toggle for Web Speech (parallel mic capture is the prime suspect for degraded recognition) | `9d97c25` |

---

## 2. Open flaws — should be fixed before the next milestone

### 2.1 The LLM has never actually run on this machine (CRITICAL for demo)
There is no `.env` / `OPENROUTER_API_KEY` anywhere, and the code default is the
**paid** `qwen/qwen-2.5-72b-instruct` endpoint. Every "Transcript Analysis" number
ever demoed here came from the keyword fallback (now loudly tagged). This is the
root of the "hi do not give me otp → SUSPICIOUS 69%" failure.
**Owner:** Dev 3 · **Fix:** see `LLM_RAG_FIX_PLAN.md` Phase 1.

### 2.2 LLM audit throttle burns quota when keywords persist
`WhisperReasoningProvider` audits **every cycle** while a high-tier keyword is in
the transcript (`trigger_llm` has no cooldown), and the webspeech hybrid mode adds
an extra evaluation cycle per 8s audio frame. On Web Speech, cycles arrive per
utterance — a 3-minute scam call can easily fire 30+ LLM calls. On OpenRouter's
free tier (50/day) that is one demo. Add a minimum-interval cooldown (e.g. 10s)
even when `trigger_llm` is true. **Owner:** Dev 2/3.

### 2.3 AASIST model file is not in the repo
`MODEL_PATH` points to `app/resources/aasist.onnx`, which doesn't exist. All
deepfake numbers come from the acoustic-heuristic mock (`AASIST-Acoustic`, energy
envelope/ZCR features). Either commit/distribute the ONNX file (Git LFS or a
download script) or present the acoustic heuristic honestly in the UI.
**Owner:** Dev 2.

### 2.4 Fusion dilutes high transcript risk when there's no audio
`EvidenceFusionEngine`: the `fused = max(fused, transcript_risk)` floor only
applies **when a deepfake score exists**. In pure text mode (Direct Transcript, or
Web Speech with voice-clone scan off), a 0.95 transcript risk can be averaged down
to ~0.60 by low heuristic/RAG scores. Inconsistent: audio presence shouldn't
change how much we trust the transcript signal. Apply the floor always, or not at
all. **Owner:** Dev 2.

### 2.5 VerificationProvider reads a one-cycle-stale verdict
Providers run concurrently (`asyncio.gather`); `VerificationProvider` reads
`session.llm_verdict` synchronously before `WhisperReasoningProvider`'s audit
returns, so the verification penalty always lags one cycle. Mostly masked by the
sticky-verdict fix, but the ordering is a trap. Either run verification after the
reasoning provider or feed it the audit result explicitly. **Owner:** Dev 2.

### 2.6 Batch upload still fabricates transcripts on Whisper failure
`whisper_service.py` returns filename-keyed **mock transcripts** when
transcription fails (old M7 flag, still unresolved). A failed upload can produce a
convincing fake analysis. Fail loudly instead. **Owner:** team decision, then Dev 2.

### 2.7 Startup blocks until three models load → "Failed to fetch"
`main.py` eager-loads StreamingTranscriber + WhisperService + AASIST during
FastAPI startup; until done, the port is closed and every frontend request shows
raw "Failed to fetch" (seen in testing right after launch — first `base` model
download can take minutes). Options: serve immediately + lazy-load, or a frontend
health-poll splash ("models warming up…"). **Owner:** Dev 1/2.

### 2.8 `run_app.bat` wipes the databases on every launch
Deletes `chroma_db` **and** `db.sqlite3` each run. Live sessions now persist call
logs (M9 groundwork) — but every restart erases history. Fine for the advisory
index (re-seeded); wrong for call logs. Stop deleting `db.sqlite3`. **Owner:** any.

### 2.9 `/analyze/history` re-runs a full analysis per row
The history endpoint calls `AnalyzerService.analyze_transcript(log.transcript)`
for **every log row** (potentially an LLM call each) just to rebuild a response
shape it then overwrites with stored values. Read from the DB only. Also: the new
fields (evidence_breakdown, reasoning_trace, deepfake label/confidence) aren't
persisted, so history loses them. **Owner:** Dev 1 (M9 history card).

### 2.10 AASIST filename/keyword demo triggers
`AASISTDetector.detect` inspects filenames/transcripts for magic keywords to force
mock spoof scores "for testing/demoing". Document it loudly or remove before
judging — an innocuous filename could flip a demo verdict. **Owner:** Dev 2.

---

## 3. Watch items from live testing (not yet root-caused)

- **Web Speech accuracy feels worse since the merge.** Recognition config didn't
  change; the mechanical difference is the **parallel second mic capture**
  (background MediaRecorder for AASIST) plus its 8s stop/start cycle, which can
  change the browser's audio processing (AEC/AGC) on some devices. A/B it with the
  new "Voice-clone scan" toggle: if accuracy recovers with it off, the fix is to
  move capture to the same MediaStream/AudioWorklet or drop hybrid capture.
- **Whisper stall past 30s** should be gone with the 15s block commit — confirm in
  a >60s session.

## 4. Improvement suggestions (nice-to-have, post-milestone)

1. `ScriptProcessorNode` is deprecated — migrate mic capture to `AudioWorklet`.
2. Persist evidence_breakdown/reasoning_trace/deepfake fields in `CallLog` (M9).
3. Coach panel TTS or vibration cue in DANGER (user may not be looking at screen).
4. Advisory links surfaced in the live view (advisories arrive in updates but are
   only shown in the final report).
5. Whisper `initial_prompt` is a good start — extend with caller-specific vocab
   (bank names, city names) and Hinglish variants; heuristic inflections
   (`arrest(ed)?`) still pending from M7 findings.
6. WS reconnect with session resume (a dropped socket currently ends the session).
