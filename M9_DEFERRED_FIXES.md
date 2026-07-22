# M9 Review — Deferred Fixes

**Date:** 2026-07-21 · **Author:** Dev 1 · **Branch:** `dev1-m9-review`
**Context:** review of Dev 2 / Dev 3's M9 work on `feature/m2-audio-services`.
Fixed in the first pass: RAG tail-truncation, report-generator event-loop
blocking, incident date, LLM prompt distortion, `deepfake_probability`,
stale report modal, `peak_risk`/`duration_s` surfacing.

**Resolved 2026-07-22: items 1–5** — see the RESOLVED banners below. Items 2 & 4
were done together in a second pass (report persistence + a sealed, read-only AI
body with always-editable complainant details). Still open: the smaller items in
§6, and the login / per-user history phase (next — the persistence layer below
was built to accept a `user_id` FK cleanly).

The items below were reviewed, understood, and **consciously deferred** — they
are not oversights. Rough order of value.

---

## 1. Negation strategy in `heuristic_scorer.py` — **RESOLVED (2026-07-22)**

**Done:** replaced `NEGATION_PATTERNS` + `_NEGATION_WINDOW` with the
protective-phrase whitelist (`PROTECTIVE_PATTERNS` matched against the clause
containing the keyword, reading forward as well as back). `_is_negated` keeps
its name and signature because `app.rag.query_engine` imports it — so the RAG
keyword-suppression path silently benefits too. Re-verified against the 20-case
set below on the **production** scorer: **20/20, 0 missed scams, 0 false
alarms.** This unblocked item 3.

---

The current backward 60-character negation window silently suppresses genuine
scam keywords. Measured on a 20-case set:

| Strategy | Score | Missed scams | False alarms |
|---|---|---|---|
| current (60-char window) | 10/20 | **9** | 1 |
| clause-scoped window | 18/20 | 1 | 1 |
| token window (k=3/4/5) | 17/20 | 0 | 3 |
| no negation at all | 15/20 | 0 | 5 |
| **protective-phrase whitelist** | **20/20** | **0** | **0** |

Every backward-window variant fails structurally: it asks "is a negation word
near this keyword?", which needs grammar to answer. Two concrete breakages —
a second keyword outside the window (`"never ask for your OTP or PIN"` — `PIN`
escapes and fires), and Hinglish postfix negation (`"OTP mat batao"`, where the
negation *follows* the keyword) which no backward window can ever catch. That
last one is a live false positive on `main` today.

**Recommended:** replace `NEGATION_PATTERNS` + `_NEGATION_WINDOW` with a closed
list of ~6 protective-advice phrasings, matched against the clause containing
the keyword (reading forward as well as back). It fails in the *safe*
direction — a missed protective phrasing costs one LLM call, which corrects
it, instead of blinding the scanner.

**Blocks item 3 below.** Effort ~1 h including tests.

## 2. `ReportModal.jsx` — victim details cannot be edited after first blur — **RESOLVED (2026-07-22)**

**Done:** deleted `handleInsertDetails` and the four `onBlur`s. Complainant
details now live in state and are **derived at output time** (`buildUserSection`
inside `getFullFinalText`), exactly like the integrity block — so the fields are
always live and a corrected loss amount always applies. Per the agreed **Option
A**, the AI audit body is **read-only and sealed**; the user's details are
composed into a separate section labelled *"COMPLAINANT-SUPPLIED — NOT part of
the AI audit seal,"* which is the honest boundary (the AI can only attest to what
it analysed). Verified via the frontend build + the persistence test.

---

`handleInsertDetails` appends the victim block guarded by
`if (!reportContent.includes('VICTIM & FINANCIAL LOSS DETAILS'))`. Correcting a
mistyped name — or, worse, a mistyped **loss amount** — silently does nothing.

**Recommended:** stop mutating the textarea. Keep the body in state and make
the victim block *derived* at output time, exactly as the integrity-hash block
already is; delete `handleInsertDetails` and the `onBlur` handlers. Removes the
whole "insert once" bug class.

Partially mitigated already: the fields now reset when a new draft loads, so a
previous complainant's details can't leak into a different incident.

**Effort ~45 min.**

## 3. Fusion weights — `transcript` 0.60 / `heuristics` 0.10 — **RESOLVED (2026-07-22)**

**Done:** reverted to `main`'s `0.45 / 0.25 / 0.20 / 0.10`. Renormalization was
**rejected**, not deferred — it removes the pre-LLM cap, and because the ratchet
floor (`0.75 × peak`, risk_engine.py) only ever rises, a keyword-noise spike
above ~0.467 latches the call in VERIFY/DANGER permanently, which the LLM's later
SAFE verdict cannot undo. The fixed-weight cap of 0.55 keeps the worst realistic
benign peak (~0.35) below the 0.35 VERIFY-exit, so pre-LLM states stay
reversible. Verified: pre-LLM loud tier-3 + 2 advisories now scores **0.45
(VERIFY)** vs 0.30 (MONITOR/SAFE) under the old weights — the blind window is
closed. Higher transcript weight bought no LLM authority anyway: the transcript
**floor** already pins the score to the LLM the instant it audits. Gated behind
item 1 (0.25 re-arms keyword false positives; the whitelist keeps them quiet).

A middle scheme (transcript 0.50 / heuristics 0.20) was analysed and set aside:
it is reversible only *by timing* (a pre-LLM verification hit reaches peak 0.50
→ floor 0.375 → latch), and it can't escape the single-dial trilemma — you
cannot get *close-the-blind-window* + *keep-benign-out-of-VERIFY* +
*provable-reversibility* from weights alone; item 1 is what breaks it.

---

Measured cost vs `main`'s 0.45/0.25 (the state before this revert):

| Scenario | main | branch |
|---|---|---|
| Early call, no LLM audit yet, loud keywords + advisory | 0.42 | **0.29** |
| Groq 429'd, weak fallback, loud keywords | 0.55 | **0.47** |
| LLM healthy, everything hot | 0.90 | 0.90 |

Fine when Groq is up; worse in exactly the two degraded modes the multi-model
429 fallback exists to handle.

Root cause is not the constant: `fuse_evidence` uses **fixed weights with no
renormalisation**, so before the first LLM audit the transcript dimension
consumes 60% of the budget while contributing 0 — mechanically capping the
early-call score at 0.40 however loud the keywords are.

**Options:** revert to 0.45/0.25 (1 line) · split to 0.55/0.15 (1 line,
arbitrary) · renormalise over dimensions with `confidence > 0` (~2 h, the
real fix).

**Do not touch until item 1 is resolved** — both change early-call
sensitivity, and tuning weights against a keyword scanner that is currently
blind on 9/12 scam lines means tuning against a broken baseline.

## 4. Report persistence — and the integrity-hash credibility problem — **RESOLVED (2026-07-22)**

**Done, the full persistence path (not just temperature):**
- **Determinism:** LLM summary `temperature 0.2 → 0.0`, timeout `8s → 10s`.
- **Storage:** four nullable columns on `call_logs` (`report_text`, `report_hash`,
  `report_version`, `report_generated_at`) via the existing additive migration —
  verified non-destructive on a copy of the real DB.
- **Cache-aware endpoint:** `/generate-report` takes `log_id` + `regenerate`.
  First open generates once and **stores**; every later open returns the stored
  document with **no LLM call**, so text and hash never drift. `regenerate=true`
  bumps `report_version` and overwrites; mid-call drafts (no `log_id`) stay
  ephemeral. Verified: reopen = 0 new LLM calls + identical hash; regenerate = v2
  + new hash.
- **Honest seal (Option A):** the SHA-256 seals the read-only AI body only; the
  document stamps `Report Version: N (regenerated)` so a redo is visible on its
  face. Two-step Regenerate button guards against accidental overwrite.
- **Plumbing:** `AnalysisResponse.id` now flows to the frontend (batch + history)
  so the report can be keyed to its call.

*(temperature 0.0 alone was the ~5-min option; we did the real persistence path.)*

---

Every modal open calls Groq fresh; nothing is stored. Beyond quota burn, at
`temperature=0.2` the same incident yields a **different document each time**,
so the SHA-256 "Legal Audit" hash changes on every regeneration of an
unchanged call. A hash that differs each time you view the same incident
argues against integrity rather than for it.

- **Cheap (~5 min):** set `temperature=0.0`. Near-deterministic, hash stable,
  no schema change.
- **Full (~3 h, needs Dev 2):** the Plan B design — `report_text` +
  `report_hash` columns, `POST` persists, `GET` returns the stored draft,
  "Regenerate" explicitly overwrites.

## 5. `/generate-report` has no verdict gate — **RESOLVED (2026-07-22)**

**Done, both halves:**
- **Honest by verdict** (`report_generator.py`): `is_complaint = label in
  {SCAM, SUSPICIOUS}`. Those keep `CYBERCRIME COMPLAINT DRAFT` + the 1930 /
  cybercrime.gov.in reporting portals. **SAFE** now renders `CALL AUDIT RECORD`
  with a neutral `DISPOSITION` section ("not a cybercrime complaint; no action
  required") and the complaint framing + portals omitted. The endpoint is now
  correct at any input with no second gate to keep in sync.
- **Pydantic request schema** (`ReportRequest` in `schemas.py`): `transcript` is
  required, so an empty `{}` POST is a **422** instead of a complaint drafted
  about "(no speech captured)". Verified: `ReportRequest()` and
  `ReportRequest(transcript="")` both raise; SAFE and SCAM payloads render the
  correct document.

This closes the latent risk that Plan B's per-history "Report" action (which
lists SAFE calls) could produce complaint drafts.

---

The "Prepare & Edit Cybercrime Complaint" button is gated in React
(`AnalysisDetails.jsx:54`, `label === 'SCAM' || label === 'SUSPICIOUS'`), so a
SAFE call cannot produce a complaint *through the app*. The endpoint has no
equivalent check:

```python
@router.post("/generate-report")
async def generate_report(data: Dict[str, Any] = Body(...)):
    return await ReportGenerator.generate_report(data)
```

`Dict[str, Any]` accepts any JSON object — no schema, no required fields, no
label check — and `ReportGenerator` fills defaults for whatever is missing.
POSTing an empty `{}` returns a complete, downloadable police complaint:

```
INCIDENT AUDIT REPORT & CYBERCRIME COMPLAINT DRAFT
National Cyber Crime Reporting Portal (cybercrime.gov.in) / Helpline 1930

Threat Evaluation Label: SUSPICIOUS (Risk Score: 0%)
Detected Scam Category: None
```

SUSPICIOUS only because that is the default on `report_generator.py:31`; a 0%
risk score under a SUSPICIOUS label is self-contradictory on the face of the
document.

**Why it matters.** A UI gate is presentation, not policy — it constrains what
a user sees, not what the server does. The concrete risk is not `curl`, it is
the next report trigger someone adds: **Plan B item 5 specifies a per-history-
entry "Report" action, and the history drawer lists SAFE calls too.** Wire that
up without re-implementing the label check and safe calls start producing
complaint drafts. This is also the one output whose downstream action is filing
with a real helpline (1930), where a knowingly false complaint carries
consequences for the complainant.

**Severity: latent, not live.** Unreachable through the current UI; found by
calling the service directly in a test. Flagged because it stays harmless right
up until a second entry point exists.

**Recommended:** rather than making the endpoint refuse low-risk input, make
the document honest about whatever it is given — SCAM/SUSPICIOUS keeps
`CYBERCRIME COMPLAINT DRAFT`; SAFE becomes `CALL AUDIT RECORD` with the
complaint framing and 1930 portal links omitted. The endpoint is then correct
at any input with no second gate to keep in sync, and a safe call still yields
a useful artifact. Alongside it, replace `Dict[str, Any]` with a Pydantic
request schema so a missing transcript is a 422 rather than a complaint about
"(no speech captured)".

**Effort ~45 min for both.**

## 6. Smaller, known, unactioned

- **`CoachPanel.jsx` reaction buttons** ("Caller Refused/Evasive", "Hostile")
  are local `useState` only — they show a static message, send nothing to the
  backend, and do not affect risk or mode. Cosmetic; could read as a live
  feedback loop in a demo.
- **`main.py` cold start** still eager-loads 2 Whisper models synchronously
  before the port opens. See `HACKATHON_ALIGNMENT_ROADMAP.md` Tier 4.2.
- **Dead AASIST files** — `deepfake_detector.py`,
  `providers/aasist_deepfake.py` are orphaned and unused. Cleanup deliberately
  skipped this pass. `CallLog.deepfake_probability` is now correctly left NULL
  ("not checked") rather than written as a false `0.0`.
- **`ReportModal` has no Regenerate button** (Plan B item 4); pairs naturally
  with item 4 above.
- **Dead `Evidence.weight` field** — every provider declares a `weight=` kwarg
  (`whisper_reasoning` 0.40, `heuristics` 0.20, `rag_advisory` 0.10,
  `verification` 0.10, `aasist` 0.20) but `fuse_evidence_list` reads only
  `ev.score` and applies its own `WEIGHTS` dict. The declared values are a
  **fossil of the pre-AASIST 5-dimension scheme** (they sum to 1.0 only with the
  removed deepfake 0.20) and now *contradict* the live weights (e.g. rag declares
  0.10, fusion uses 0.20). No wrong output today, but two footguns: it misleads a
  reader, and the natural "wire `ev.weight` into fusion" refactor would silently
  flip every weight. ~10 min fix: make `WEIGHTS` the single source of truth
  (delete or sync the per-provider kwargs). Do it next time fusion is touched.
