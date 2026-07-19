# LLM / RAG / AI Fix Plan — From Keyword Matching to Understanding

**Date:** 2026-07-19 · **Branch:** `feature/m7-live-ui` · **Author:** Dev 1
**Status:** ANALYSIS + PLAN ONLY — nothing here is implemented yet, by design.

---

## 1. The failure, dissected

Direct Transcript input: **"hi do not give me otp"**

What the system said:
- Threat level **69% — SUSPICIOUS**, category **Bank Impersonation (KYC/OTP)**
- Transcript Analysis **95%** (trace: "Confidence: 100%")
- Scam Heuristic Score **87%**

What a human sees: someone *warning* against sharing an OTP — the exact opposite
of a scam demand. The system scored the *presence of the word*, not the meaning of
the sentence. Three separate engines all made the same category of mistake:

1. **"Transcript Analysis" was never an LLM.** There is no `OPENROUTER_API_KEY` on
   this machine and the coded default is the *paid* Qwen endpoint, so
   `evaluate_transcript` always lands in `_get_fallback_mock`, which does:
   `any(kw in text for kw in ["otp", "bank", ...]) → risk 0.95`. The 95% "LLM"
   number **is keyword matching wearing an LLM costume**. (The trace now at least
   tags it `[FALLBACK MOCK ANALYSIS - NO LIVE LLM]`.)
2. **HeuristicScorer has no notion of negation or speaker.** `otp` is a high-tier
   keyword → 0.87, whether the sentence is "share your OTP now" or "never share
   your OTP". By design it's a cheap tripwire — the problem is what happens next:
3. **Fusion trusts the mock like a model.** Transcript signal gets weight 0.40 and
   confidence 1.0 *regardless of which engine produced it*. Keyword-mock +
   keyword-heuristic = two correlated votes for the same mistake — 60% of total
   weight agreeing on nonsense, displayed as "Confidence: 100%".

**Bottom line:** the only component capable of understanding "do not" (a real LLM)
is the only component not actually running.

---

## 2. The plan

### Phase 1 — Put a real LLM in the loop (Dev 3 · ~1 hour · DEMO-CRITICAL)
From `LLM_NOTES.md` (2026-07-18): **Groq + `llama-3.3-70b-versatile`** — free, no
card, ~1,000 req/day, OpenAI-compatible (≈3-line change: `base_url`, model, key
env var), sub-second inference which makes per-cycle live audits actually viable.
Alternatives: Gemini Flash (1,500/day free) or an OpenRouter `:free` model
(zero code change but 50 req/day).
- Add `backend/.env.example` documenting `OPENROUTER_API_KEY` / `GROQ_API_KEY`,
  `OPENROUTER_MODEL`; each dev gets a key locally. Never commit real keys.
- Acceptance: "hi do not give me otp" → SAFE with an explanation that mentions the
  speaker is *refusing* to share an OTP; backend log shows a real HTTP call.

### Phase 2 — Stop burning quota (Dev 2/3 · ~30 min)
`trigger_llm` audits every cycle while a scam keyword is visible — no cooldown.
Add a minimum interval (~10s) between audits even when triggered, and skip audits
when the transcript hasn't changed. Budget: a 3-min call should cost ≤ ~12 calls.

### Phase 3 — Negation guardrail in the heuristics (Dev 2 · ~1 hour)
Keep the keyword tripwire but make it negation-aware: if a tier keyword is
preceded within ~4 tokens by `don't | do not | never | won't | wouldn't | refuse
to | warning about`, suppress or halve that hit. This is a guardrail, not NLP —
the LLM stays the semantic authority; the heuristic just stops actively lying.
Also add the long-pending inflection variants (`arrest(ed|ing)?`, `blocked?`).

### Phase 4 — Fusion honesty: score the engine, not just the text (Dev 2 · ~2 h)
- The fallback mock must self-identify (e.g. `"engine": "fallback"` in its result)
  and be fused with reduced weight (~0.15) and capped confidence (~0.4) so
  keyword-only evidence can never print "Transcript 95% (Confidence 100%)".
- Resolve the asymmetry where `max(fused, transcript_risk)` applies only when a
  deepfake score exists (see FLAWS_AND_IMPROVEMENTS.md §2.4).
- UI: show an "engine" badge on the transcript row — *LLM* vs *keyword fallback* —
  so a demo audience is never misled about what produced the number.

### Phase 5 — RAG quality (Dev 3 · ~2 h)
- The pure-Python fallback store now filters stopwords and requires ≥2 shared
  meaningful words — calibrate the real ChromaDB path the same way: measure
  distances for ~10 benign and ~10 scam transcripts, then justify the 1.25
  threshold with data (it was a guess; the fallback path proved a threshold can
  silently no-op).
- Score matches by similarity, not count: `count * 0.5` says two weak matches are
  certainty. Use `1 - best_distance` (normalized) as `rag_match` instead.
- Advisories cached in `session.llm_advisories` never expire during a call —
  re-query on major transcript growth, drop when topics no longer match.

### Phase 6 — Prove it: a tiny eval harness (Dev 1 · ~2 h)
`backend/scratch/eval_transcripts.py` with ~25 labeled one-liners across:
scam demands · benign-with-keywords ("my bank called me back, all fine") ·
warnings/negations ("do not share your otp") · lottery/police variants ·
plain small talk. Script runs the full analyze path, prints a confusion table.
Run before/after Phases 1–5; the negation set going green is the definition of
"the AI is fixed". Also becomes the regression gate for future prompt changes.

---

## 3. Sequencing & effort

| Phase | Owner | Effort | Blocks demo? |
|---|---|---|---|
| 1. Real LLM (Groq) | Dev 3 | ~1 h | **YES** |
| 2. Quota cooldown | Dev 2/3 | 30 min | YES (quota death mid-demo) |
| 3. Negation guardrail | Dev 2 | 1 h | partially |
| 4. Fusion honesty | Dev 2 | 2 h | no, but embarrassing without |
| 5. RAG calibration | Dev 3 | 2 h | no |
| 6. Eval harness | Dev 1 | 2 h | no — but run it before judging |

Phases 1–2 alone fix the flagged screenshot for any machine with a key. Phases
3–4 make the system degrade honestly when the key is missing — which is exactly
the situation this machine has been in the whole time.
