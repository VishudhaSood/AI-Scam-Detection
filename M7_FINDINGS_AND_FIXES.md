# Milestone 7 — Demo Findings & Proposed Fixes

**Status:** M7 demo checkpoint PASSED on 2026-07-18 (live mic → streaming
transcript → heuristic risk → final report, on the phone-on-speaker setup).
This document records what broke during integration, what was hotfixed, what
issues the live demo surfaced, and the proposed fixes with owners. Implementation
of the "Proposed fixes" section is **not started yet** — we'll schedule it
together before Milestone 8.

---

## 1. Integration hotfixes already applied (heads-up to Dev 2 / Dev 3)

These were demo-blockers found while integrating the three M7 branches, fixed
on `hotfix/m7-whisper-cuda-fallback`. They touch files outside Dev 1's lane —
review requested from their owners.

### 1a. CUDA deadlock froze live sessions (fixed — `backend/app/services/`)

**Symptom:** live session connected, then no updates ever arrived; server
worker thread frozen after the first audio chunk.

**Root cause:** the dev machine has an NVIDIA driver but no CUDA runtime
(`cublas64_12.dll` missing). `WhisperModel(device="cuda")` **constructs
successfully anyway** — ctranslate2 defers DLL loading to the first inference —
so the existing try/except CUDA→CPU fallback never fired. The first real
transcription then failed, and (nondeterministically) later native calls
**deadlocked the whole process** via poisoned Windows DLL-loader state.

**Fix applied:** new `services/cuda_check.py` — checks for the CUDA runtime
with a safe `ctypes` load *before* ctranslate2 is allowed anywhere near CUDA.
If absent, both `StreamingTranscriber` and `WhisperService` (batch path shares
the process!) go straight to CPU int8. On machines with real CUDA, GPU is still
used. Commits `7a5c5a4` + `932aea7`.

**Lesson for all of us:** "constructed successfully" ≠ "works" when a library
lazy-loads its backends. Probe preconditions with something that can't hurt you.

### 1b. Merge-day notes

- Dev 2's stub `heuristic_scorer.py` conflicted with Dev 3's real one at merge
  (both created the same path). Resolved: Dev 3's version kept. Going forward,
  stubs for another dev's module should live in the consumer's file behind a
  guarded import (as `api/live.py` does), not at the owner's real path.
- A `.gitignore` change on Dev 2's branch re-tracked `local_session_history.md`
  (deliberately ignored). Restored during merge.
- Reminder: M7 branches should follow the plan's names (`feature/m7-stream-core`
  was pushed as `feature/m2-audio-services`).
- Dev 3's `is_text_only` bypass in `risk_engine.py` + `analyze.py` was accepted
  (good fix — text-only audits no longer polluted by the mock deepfake weight),
  but per our protocol, cross-boundary changes need a heads-up in team chat first.

---

## 2. Issues observed in the live demo

### Issue A — Timer jumps in steps of 5–10s instead of ticking

The UI clock renders `elapsed_s` from server updates, which arrive only per
processing cycle (~5s, later when CPU transcription runs long). Correct data,
bad UX: the clock freezes then leaps. (Design decision by Dev 1 — server
authority was the wrong trade-off for a continuously-watched element.)

### Issue B — Poor voice recognition

Real call test transcribed "OTP" as "ODB"/"ROTB" and "HSBC" as "HSPC". Causes,
by impact:
1. Whisper **tiny** int8 on CPU — weakest model, textbook failure mode on short
   technical tokens and accented English.
2. Zero decoding context: no `language="en"` (re-detects language every block),
   no `initial_prompt` (no vocabulary bias toward our domain terms).
3. Speakerphone acoustics (accepted by design; can't fix physics).

### Issue C — The scam was MISSED at risk 0.05 (most important finding)

The demo transcript contained **"then you will be arrested"** — correctly
transcribed — and the score stayed 0.05/SAFE. Why: the tier-3 pattern is
`\barrest\b`, and in "arrest**ed**" the boundary never fires. The same word
boundaries that stop "pin" matching inside "shopping" also stop "arrest"
matching "arrested". Patterns need explicit inflection variants. ("OTP" was
also lost, but that was Issue B's fault.)

### Issue D — General glitchiness

Mostly A, plus: the partial transcript legitimately rewrites itself each cycle
(block-commit design — expected, stays), no auto-scroll on the transcript box,
risk number snaps instead of easing.

---

## 3. Proposed fixes (NOT yet implemented — for team discussion)

| # | Fix | Owner | Files |
|---|-----|-------|-------|
| 1 | **Steady clock:** client-side 1s ticker for display; server `elapsed_s` kept as drift-corrector (snap if divergence > ~2s). Local optimistic display + server reconciliation — standard live-UI pattern. | Dev 1 | `LiveCallMonitor.jsx` |
| 2 | **UI calm:** auto-scroll transcript to newest text; don't flash "Listening…" once text exists; ease the risk number transition. | Dev 1 | `LiveCallMonitor.jsx` |
| 3 | **Transcription quality:** (a) model `tiny` → `base` int8 — *gated on a timing test* on the demo machine (must fit the cycle budget, else stay tiny); (b) pass `language="en"` + `initial_prompt` with scam-domain vocabulary (OTP, KYC, HSBC, arrest, lottery, AnyDesk, …) — biggest accuracy-per-cost win; (c) run Whisper every **2nd** chunk (10s cadence) while heuristics + updates keep the 5s cadence — halving model cost pays for `base`. | Dev 2 | `streaming_transcriber.py`, `live_session.py` |
| 4 | **Heuristic robustness:** add inflection variants to keyword patterns — `arrest(ed|ing)?`, `suspend(ed)?`, `block(ed)?`, etc. This alone would have caught the demo call at tier 3 despite the bad transcription. | Dev 3 | `heuristic_scorer.py` |

**Suggested order:** 1+2 (frontend, zero risk) → 3 (measure first, then apply)
→ 4 (small, high value). All three lanes can go in parallel like the milestone
work itself.

---

## 4. Current git state

- `main` = full M7 merge (`a333238`).
- `hotfix/m7-whisper-cuda-fallback` (`7a5c5a4`, `932aea7`) = CUDA fixes,
  **verified working in the live demo, not yet merged to main / pushed**.
- Next action: merge the hotfix into main and push, then plan the fixes above.
