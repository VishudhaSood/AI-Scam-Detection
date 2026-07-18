# AI Scam Detection — Architecture Improvements & Feasibility Analysis

> Critical analysis of 7 proposed enhancements to move the platform from a
> post-hoc audio-file auditor to a real-time call companion.
> Grounded in the current codebase (FastAPI backend + React frontend +
> Whisper/RAG/Qwen pipeline).

---

## 0. The constraint that governs 5 of the 7 ideas

Ideas **2, 3 (trigger), 5, 6, and 7** all depend on one thing: **capturing the
scammer's live voice during the call.** There is a hard platform wall here:

**No third-party app on iOS or modern Android can tap the audio of a normal
cellular / PSTN phone call.**

- **iOS:** zero API for call audio. CallKit tells you a call is happening; it
  never gives you the audio. The microphone is also unavailable to your app
  while a native call owns the audio session.
- **Android:** `AudioSource.VOICE_CALL` / `VOICE_DOWNLINK` was locked to
  system/OEM apps from Android 10 onward. Your app can record *your own*
  microphone, but not the scammer's downlink stream on a regular call.

Our current code already works around this without realizing it: `getUserMedia`
in the browser only ever captures the **microphone**. The only capture paths
that actually exist for us are:

1. **Speakerphone + microphone (acoustic capture).** User puts the call on
   speaker; our app listens through the mic and hears *both* sides through the
   air. This is the realistic unlock — works on web, Android, and iOS, and is
   genuinely how a shippable version would work.
2. **VoIP / call-forwarding bridge** (forward unknown numbers to a Twilio-style
   number that bridges and streams audio). Clean audio, but heavy, and drags in
   call-recording-consent law.

**Key consequence:** "Convert to a mobile app" does **not** unlock live call
tapping. Mobile is *more* restrictive than the current desktop/web setup, not
less. The real architectural decision is **how we capture audio** — and for a
hackathon the answer is **speakerphone + mic streamed over a WebSocket.**

---

## 1. Verdict — what will work, ranked

| Idea | Verdict | Why |
|---|---|---|
| **#4 Report button (pre-filled draft)** | ✅ **Do it first** | Highest value-to-effort. Pure backend + UI, reuses the LLM output we already generate. Zero platform risk. |
| **#2 + #5 Live streaming + moving risk score** | ✅ **The core "wow", real effort** | One feature really: stream audio → incremental transcript → live risk gauge. Feasible via WebSocket + chunked Whisper + speakerphone capture. Biggest lift. |
| **#1 Web/PWA now; Android native for interception** | ✅ **Feasible, but reframe** | Keep the FastAPI backend as-is; swap the client. PWA is trivial. Native Android only needed to *auto-detect* unknown numbers. |
| **#3 Only listen to unknown numbers** | ⚠️ **Works, but needs native Android** | Simple logic (`CallScreeningService` + contacts check), impossible on web/iOS. Gated on going native. |
| **#6 Identify speaker vs caller (diarization)** | ⚠️ **Hardest, least essential** | Real-time diarization is advanced, and we mostly don't need it — scam content is scam content regardless of who says it. |
| **#7 Suggest questions to keep the scammer talking** | 🛑 **Trivial to build, reframe on safety** | LLM part is easy. But coaching a likely victim to stay on the line and interrogate a scammer runs against consumer-safety guidance and can cause harm. Reframe it. |

---

## 2. Idea-by-idea analysis

### #1 — Mobile app / web application
The backend (FastAPI, Whisper, RAG, risk engine, SQLite) is cleanly separated
from the client — good architecture, and it means the client is swappable
without touching the brain.

- **PWA (recommended near-term):** wrap the existing React app as an installable
  PWA. Gets "app on the home screen," mic access, cross-platform. **Cannot** read
  the caller's number or run reliably in the background.
- **Native Android (recommended if #3 matters):** unlocks caller-number detection
  and call-state awareness. Still can't tap call audio (speakerphone workaround
  required).
- **Native iOS:** most locked. Can label/block numbers (Truecaller-style) but no
  audio, no live analysis. Skip for the hackathon.

**Flaw to avoid:** don't assume "mobile" buys live-call access. It doesn't.
Decide the capture method first.

### #2 — Live recording + real-time processing
The pipeline today is **batch**: record whole call → one upload → transcribe
whole file → one LLM call → result. Real-time needs three changes:

1. **Streaming capture:** replace the single `POST /analyze` with a **WebSocket**
   that streams ~2–5s audio chunks.
2. **Incremental STT:** Whisper isn't natively streaming, so window it with a
   rolling buffer + voice-activity detection (VAD). The `tiny` model keeps
   latency low.
3. **Incremental analysis:** run cheap heuristics on every chunk; throttle the
   expensive Qwen call to every ~15–20s or on trigger keywords (cost + latency
   control).

**Feasible, and it's the headline feature.** **Flaws:** chunk-boundary context
loss in Whisper; early-call false positives (little evidence yet); repeated-LLM
cost; and note the **deepfake detector is currently a mock** (filename keywords +
seeded random in `whisper_service.py`) — a *real* real-time anti-spoof model
(RawNet2 / AASIST class) is a separate workstream, so keep it mocked for the demo
and label it clearly.

### #3 — Only listen to unknown numbers
Sensible (fewer false positives, better privacy, less compute). On **Android**: a
`CallScreeningService` gives the incoming number; check it against
`READ_CONTACTS`; if unknown, fire a notification ("Unknown caller — tap to start
Scam Shield, put the call on speaker"). **Flaw:** impossible on web/iOS.
**Improvement:** don't fully automate — *offer* to start monitoring, and add an
allowlist/denylist. A number-reputation lookup (Truecaller-style) is tempting but
is scope creep for a hackathon.

### #4 — Report button with a pre-written report
Strongest quick win. We already have the transcript, risk score, category, LLM
explanation, and matched RBI/CERT-In advisories — a ready-made complaint draft.
Generate a structured report and let the user file it.

**Critical nuance — don't over-promise "report to officials":** there's no public
API to auto-file with cybercrime portals, and auto-submitting unverified reports
is legally and ethically risky (false reports, spam). Make it
**human-in-the-loop**: generate the draft, then deep-link / share-intent /
pre-filled email to the right authority (in India: the National Cyber Crime
Reporting Portal / 1930 helpline; DoT's **Chakshu** for spam/fraud; RBI Sachet).
Attach the evidence bundle (transcript, timestamp, caller number, risk score,
audio). The *user* reviews and submits.

### #5 — Continuously changing risk score
This is the **UI face of #2** — we already have `RiskGauge.jsx`. Once streaming
exists, emit a score every N seconds and animate the gauge. **Flaws & the fix:** a
raw live score **flickers** and looks untrustworthy. Make it
**evidence-accumulating**, not jittery: smooth with an EMA / hysteresis so the
score *ratchets up* as red flags appear rather than bouncing, and show a
**confidence band** early in the call (low evidence = wide band) instead of a
false-precision number. That single design choice is the difference between
"impressive" and "buggy-looking."

### #6 — Identify who is the speaker vs the caller
Two sub-problems: (a) **diarization** — split audio into "speaker 1 / speaker 2"
(pyannote.audio / WhisperX), and (b) **labeling** which one is the scammer. Batch
diarization is doable; **real-time diarization is genuinely hard** and
GPU-hungry. With speakerphone capture we get "speaker 1/2," not labels — we'd
need voice enrollment of the user, or a loudness heuristic (user's direct voice
is louder than the speaker-played caller), both fuzzy.

**Recommendation: deprioritize.** Least essential to the value prop and the
hardest to do live. If wanted, do near-real-time diarization on the rolling
buffer with WhisperX and label speakers by a simple heuristic — and set
expectations that "which one is the scammer" won't be reliable.

### #7 — Suggest questions to keep the scammer occupied
Technically the easiest of all — add a second LLM output field with 2–3 suggested
lines. **But the goal as written is a problem, and this is the one place to
stop:**

Coaching a likely victim to **stay on the line and interrogate the scammer to
"gather info"** is the opposite of what every fraud-prevention body advises (the
safe action is *hang up*). Prolonging engagement is exactly how social
engineering succeeds. It also nudges ordinary users into *scambaiting*, which
carries real personal risk and, depending on jurisdiction, call-recording-consent
exposure. And it's unnecessary: the risk engine already classifies without the
user extracting a confession.

**Reframe that keeps the demo value and drops the harm:** turn it into
**defensive verification prompts + a clear exit**. Safe, non-escalating lines that
*expose* a scammer without prolonging exposure — "Which branch are you at? I'll
call the official number back myself," "Send that to me in writing on your
official email" — paired with a prominent **"Do not share OTP / do not pay / hang
up & report"** action when risk is high.

---

## 3. Recommended target architecture

Module boundaries already support this — most of the change is at the **edges**:

- **Client:** Android app (for #3) or PWA. On an unknown incoming call → notify →
  user puts call on **speaker** → app captures **mic** and opens a **WebSocket**,
  streaming audio chunks.
- **Backend (new streaming path alongside the existing `POST /analyze`):**
  `WS /ws/analyze-stream` → rolling buffer + VAD → chunked `faster-whisper` →
  incremental transcript → per-chunk heuristics + throttled Qwen → push
  `{partial_transcript, risk_score, confidence, red_flags, safe_actions}`. Keep
  session state in memory keyed by `session_id`; **persist to SQLite on call end**
  (reuse `crud.save_analysis_result`).
- **Risk engine:** add temporal smoothing / evidence accumulation / confidence
  (extends the existing `RiskEngine`).
- **On call end:** generate the #4 report draft from the accumulated transcript +
  advisories.

**Two things on the record for the team:**
- Call-recording **consent law** varies by country (many are two-party consent) —
  document it even if we don't solve it.
- Keep **government reporting human-in-the-loop**.

---

## 4. Suggested build order

1. **#4 Report generator** (backend report builder + share/email UI) — safe, fast, high value.
2. **#2 + #5 Streaming pipeline** (WebSocket endpoint + chunked Whisper + live gauge with smoothing) — the core experience.
3. **#1/#3 Client** (PWA first; Android `CallScreeningService` if unknown-number auto-trigger is required).
4. **#7 (reframed)** defensive verification prompts + hang-up/report guidance.
5. **#6 Diarization** — only if time remains; batch/near-real-time, expectations managed.
