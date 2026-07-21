# M9 Review — Deferred Fixes

**Date:** 2026-07-21 · **Author:** Dev 1 · **Branch:** `dev1-m9-review`
**Context:** review of Dev 2 / Dev 3's M9 work on `feature/m2-audio-services`.
Fixed already this pass: RAG tail-truncation, report-generator event-loop
blocking, incident date, LLM prompt distortion, `deepfake_probability`,
stale report modal, `peak_risk`/`duration_s` surfacing.

The items below were reviewed, understood, and **consciously deferred** — they
are not oversights. Rough order of value.

---

## 1. Negation strategy in `heuristic_scorer.py` — DECISION PENDING

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

## 2. `ReportModal.jsx` — victim details cannot be edited after first blur

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

## 3. Fusion weights — `transcript` 0.60 / `heuristics` 0.10

Measured cost vs `main`'s 0.45/0.25:

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

## 4. Report persistence — and the integrity-hash credibility problem

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

## 5. Smaller, known, unactioned

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
