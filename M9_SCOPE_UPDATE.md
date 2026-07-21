# Milestone 9 — Scope Update

**Date:** 2026-07-20 · **Author:** Dev 1 · **Branch:** `main` @ `e739681`
**Why this doc exists:** `NEW_team_collaboration.md` (the doc that specified M9 §4)
was deleted from `main` in commit `21166c0` along with `NEW_ARCHITECTURE.md` and
`Improvements.md`. `HACKATHON_ALIGNMENT_ROADMAP.md` still cites
`NEW_team_collaboration.md §4` as "M9 as written — no new spec needed, execute the
doc." That's no longer true: the doc is gone, and more importantly, **parts of M9
have already been built — informally, and differently from how it was specified.**
This document recovers the original spec, reconciles it against what actually
shipped in the last three commits to `main` (`8efa036`, `21166c0`, `8b9e9ae`), and
gives the revised task list.

---

## 1. What M9 originally said (recovered from `NEW_team_collaboration.md §4`, git history)

**Goal:** every finished live call is persisted with its score timeline; a complaint
draft is generated; the user can review, edit, copy, and send it via official
channels; history shows past sessions with sparklines.

| Owner | Deliverable |
|---|---|
| Dev 1 | `ReportModal.jsx` (editable draft, copy button, `mailto:` link, cybercrime.gov.in / 1930 / Chakshu / RBI Sachet links); `backend/app/api/report.py` (`POST`/`GET /api/v1/report/{log_id}`); `ReportDraft` schema; wire auto-open on session end + DANGER-mode button + history per-entry action; render `score_timeline` sparklines |
| Dev 2 | Extend `CallLog` with `session_id, caller_number, duration_s, peak_risk, score_timeline (JSON), report_text`; `LiveSession.finalize()` persisting the full session incl. score timeline; `crud.save_report_text` + fetch helpers; finalize must also run on abrupt WS disconnect |
| Dev 3 | `services/report_generator.py` — `ReportGenerator.generate(call_log)`, LLM-drafted formal complaint citing transcript quotes + matched advisories, **never inventing facts**; template fallback with no API key |

---

## 2. What's already shipped that overlaps M9 (found while reviewing `main`)

This did **not** go through the `feature/m9-*` branches above — it landed inside
the same commits that did the LLM_RAG_FIX_PLAN work (`8efa036`, `8b9e9ae`):

- **Complaint draft — done, but as a different design.** `AnalysisDetails.jsx`
  now has a "📥 Download Complaint Draft (1930)" button. It's a **pure frontend,
  static JS template string** filled from fields already in `AnalysisResponse`
  (label, risk, category, explanation, transcript, advisories), downloaded as a
  `.txt`. There is no `report_generator.py`, no `/api/v1/report/{log_id}`, no LLM
  call, no `report_text` persistence, and no edit-before-send step — you get the
  file immediately, already finished.
- **History — done, but reusing the old endpoint.** `Dashboard.jsx` has a
  "📜 Past Audits" drawer calling the *existing* `GET /api/v1/analyze/history`.
  It is not session-aware (no `score_timeline`, no sparkline, no `caller_number`,
  no `duration_s`) because those `CallLog` columns don't exist yet — `models.py`
  is unchanged from before M9.
- **Live persistence already happens**, and already has a Milestone-9 comment on
  it: `live.py`'s `finally` block calls `crud.save_analysis_result(db, final)` on
  every session end, **including abrupt disconnect** (that part of Dev 2's spec
  is effectively satisfied by code that predates the formal M9 branches).
- **AASIST/deepfake fully removed** (fusion, orchestrator, schemas, live payload,
  frontend tiles) — the parallel mic capture it needed was degrading Web Speech
  accuracy, which is exactly the "watch item" flagged in
  `FLAWS_AND_IMPROVEMENTS.md` §3. This simplifies M9: no `deepfake_model`/
  `deepfake_probability` field to persist or cite in a report. `CallLog.
  deepfake_probability` is now a dead column (always `None`) — harmless, worth
  dropping whenever a real migration happens.

## 3. What M9 still needs (the real remaining scope)

1. **`CallLog` schema extension** — `session_id`, `caller_number`, `duration_s`,
   `peak_risk`, `score_timeline` (JSON), `report_text` are still missing. Note:
   `run_app.bat` no longer wipes `db.sqlite3` on every launch (fixed this pass),
   which is good for history but means a schema change now needs everyone to
   either delete their local `db.sqlite3` once or the team adds a tiny migration
   — flag this in team chat before merging, it wasn't a concern under the old
   "wipe every run" behavior.
2. **Score timeline capture** — nothing currently samples `risk_smoothed` per
   cycle into a list. Needed for both the sparkline and for a report that can
   say "risk climbed from 20% to 90% over the call."
3. **Decide the complaint-draft architecture**: keep the static frontend
   template (already shipping, zero LLM cost, works offline) or still build the
   spec'd `report_generator.py` (LLM-grounded, cites exact transcript quotes and
   matched advisories, editable before sending, persisted so it's the same
   report if you reopen history). Recommendation below.
4. **History drawer needs session fields** once #1/#2 land — sparkline, caller
   number, duration.
5. **`get_history` re-analysis bug** — fixed this pass (see chat summary); no
   longer part of M9's remaining work.

## 4. Recommendation

Don't rebuild the complaint draft from scratch — the static version already
closes the PS's "guided reporting" gap and costs nothing. Treat M9 as three
narrower tasks instead of the original three-branch plan:

- **Dev 2:** schema extension + score-timeline capture in `live_session.py`
  (append `risk_smoothed` to a list each cycle, pass it through `finalize()`).
  This is the only piece with no existing substitute.
- **Dev 3 (optional upgrade, not blocking):** if time allows, promote the static
  template to a real `report_generator.py` call *only* for the LLM-drafted
  narrative paragraph, keeping the transcript/advisory citation logic
  deterministic (never let the LLM invent facts, per the original spec's own
  rule). Low priority — the static version already demos fine.
- **Dev 1:** once `score_timeline` exists, add the sparkline to the history
  drawer and a caller-number/duration column. The `ReportModal.jsx` edit-before-
  send flow is the one original-spec item with no current substitute at all —
  worth adding only if `HACKATHON_ALIGNMENT_ROADMAP.md` Tier 1 items (digital-
  arrest naming, message-checker tab, number reputation) aren't higher-value use
  of the remaining time. Given judging weights (Business Impact 25%, Innovation
  25%), Tier 1.4/1.1/2.3 likely score better per hour than polishing the report
  modal further.

Net effect on the roadmap's Tier 0.1 ("M9 as written, no new spec needed —
execute the doc"): **that's no longer accurate.** Half of M9 shipped already,
in a simpler form, inside unrelated commits. The remaining half is smaller than
originally scoped (just the DB extension + timeline), which frees up time that
the roadmap's suggested order can reallocate to Tier 1.
