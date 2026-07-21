# M9 Report Generator — Two Paths

**Date:** 2026-07-20 · **Author:** Dev 1 · **Companion:** `M9_SCOPE_UPDATE.md`
**Context:** `AnalysisDetails.jsx` already ships a "📥 Download Complaint Draft
(1930)" button — a static frontend template, not the LLM-backed
`report_generator.py` the original M9 spec called for (recovered from
`NEW_team_collaboration.md §4`, since deleted from `main`). Both plans below
assume the same **shared prerequisite** (Dev 2, needed for the history
drawer's sparklines either way, not a differentiator):

> **Shared: `CallLog` schema extension.** Add nullable columns `session_id`,
> `caller_number`, `duration_s`, `peak_risk`, `score_timeline` (JSON text) to
> `backend/app/database/models.py`. In `live_session.py`, append
> `risk_smoothed` to a `self.score_timeline: list[float]` each cycle; in
> `live.py`'s finalize path, pass `duration_s=elapsed_s`,
> `peak_risk=max(timeline or [0])`, `score_timeline=json.dumps(timeline)`
> through to `crud.save_analysis_result`. **Since `run_app.bat` no longer
> wipes `db.sqlite3` on every launch**, flag this in team chat before merging
> — everyone should delete their local `db.sqlite3` once, or the app will hit
> `sqlite3.OperationalError: no such column` on their existing file.
> **Effort: 3–4 h.**

Where the two paths differ is what "the report" actually is.

---

## Plan A — Keep the static template, finish M9 around it

**Philosophy:** the current draft is a deterministic function of fields
already trusted elsewhere in the UI (risk, label, category, explanation,
transcript, advisories). Nothing in it can hallucinate — that's a genuine
safety property for a document meant to go to police. Treat "report
generation" as functionally done, and spend the rest of the M9 budget on
persistence, richness, and reach — no new backend surface, no new API cost.

One structural fact worth knowing before scoping this: `AnalysisDetails.jsx`
(which owns the button) already renders in **all three places** a report
would be needed — the batch-analyze result tab, the live-session final view
(`LiveCallMonitor.jsx:476`), and history-item selection
(`Dashboard.jsx: handleSelectHistoryItem` → `setResult(log)`). So "wire it up
everywhere" is mostly already done structurally; the work below is content
and polish, not plumbing.

### Tasks

1. **Dev 1, ~1–2 h — enrich the template.** `handleDownloadComplaint()` in
   `AnalysisDetails.jsx` currently uses risk/label/category/explanation/
   transcript/advisories. Add: `reasoning_trace` as bullet points, `red_flags`
   list, and (guard for `undefined` — only present on the live final object,
   not batch/history) `suggested_questions` asked and `safe_actions` given
   during the call, so the report shows the actual verification exchange, not
   just the verdict.
2. **Dev 1, ~30 min — official links.** Add DoT Chakshu and RBI Sachet links
   alongside the existing cybercrime.gov.in / Helpline 1930 (the original
   spec named all four; the current draft only has two).
3. **Dev 1, ~2–3 h — history sparkline + duration/caller columns.** Once the
   shared `score_timeline`/`duration_s` columns exist, render them in the
   "📜 Past Audits" drawer (small inline SVG polyline, ~40 lines, no chart
   library — 12 sampled points is plenty).
4. **Dev 1, ~1 h, optional (Tier 1.2 idea) — integrity hash.** Client-side
   `crypto.subtle.digest('SHA-256', ...)` over the report text, shown in the
   download-confirmation toast. Free "auditability" talking point since the
   text is already fully deterministic.
5. **Dev 1, ~1 h, optional — mid-call access.** Right now the button only
   appears after the call ends. Add a "Prepare complaint now" shortcut in the
   DANGER `CoachPanel` banner so a user who needs to act *during* the call
   (not after hanging up) isn't blocked.

**Total: ~1 day, entirely Dev 1 + Dev 2's shared prerequisite. Dev 3 stays
free for `HACKATHON_ALIGNMENT_ROADMAP.md` Tier 1 items (digital-arrest corpus,
message-checker tab).**

**Honest limitations to state to judges if asked:** no edit-before-filing
step; the "explanation" text is whatever the audit engine already produced
for the live UI, not phrasing specifically composed for a police report;
advisories are re-looked-up fresh each time (via the `get_history` fix this
pass), so a historical report can show slightly different advisory matches
than what displayed live if the knowledge base changes in between — unlikely
mid-hackathon, worth one sentence in a "known limitations" README section.

---

## Plan B — Build the original spec, improved with an anti-hallucination guardrail

**Philosophy:** the original M9 design (editable, LLM-drafted, persisted,
regenerable) is more capable and closer to "legally admissible." Its own
spec already anticipated the risk: *"the prompt must forbid inventing details
not present in the transcript/metadata — a fabricated complaint is worse than
none."* The improvement here is making that a structural guarantee rather
than a prompt instruction the LLM might ignore: **the LLM only ever writes
one paragraph; every fact in the document is inserted deterministically.**

### Tasks

1. **Dev 2, ~1 h on top of the shared prerequisite** — add nullable
   `report_text` column to `CallLog`; `crud.save_report_text(log_id, text)` /
   `crud.get_report_text(log_id)`.
2. **Dev 3, ~2–3 h — `backend/app/services/report_generator.py`.**
   `ReportGenerator.generate(call_log) -> str`:
   - **Deterministic assembly (no LLM):** incident date/time, caller number,
     category, risk score/label, verbatim transcript sentences that matched a
     red-flag keyword, matched advisory citations (title + source + url).
     This part is identical in spirit to Plan A's template — reuse it as the
     "facts" section.
   - **LLM-authored, one paragraph only:** prompt Groq for a single "Executive
     Summary" paragraph, given *only* the assembled facts above as context,
     with an explicit system instruction: *"Write one summary paragraph using
     only the facts provided. State no name, amount, date, or claim that is
     not present in the input. If you are not given a fact, do not mention
     it."* This bounds the model to synthesis/tone, not fact invention —
     the actual defense against hallucination is structural (it never sees
     the raw transcript to freelance from), not just an instruction.
   - **Fallback:** when no API key or the call fails, skip the LLM paragraph
     entirely and use Plan A's static phrasing instead — same offline-first
     pattern as the rest of the stack. Never block report generation on LLM
     availability.
   - Scratch-test against the three main scam categories + a benign call
     (confirm it refuses to write a report claiming a scam that didn't
     happen — test that the fallback path is what fires when risk is low).
3. **Dev 1, ~3–4 h — `backend/app/api/report.py`.** `POST /api/v1/report/
   {log_id}` (generate or regenerate — calls `ReportGenerator`, persists via
   Dev 2's helper), `GET /api/v1/report/{log_id}` (fetch persisted text, 404
   if none yet). Add a `ReportDraft` schema (`log_id`, `report_text`,
   `generated_at`).
4. **Dev 1, ~4–5 h — `ReportModal.jsx`.** Editable `<textarea>` pre-filled
   from the draft, "Regenerate" button, copy-to-clipboard, a `mailto:` link
   (note: mailto has practical length limits in most clients — treat it as
   "start a draft email," not a guaranteed full-body send; copy-paste stays
   the primary path), the four official links, and explicit copy stating the
   user reviews and files it themselves — matches the original spec's own
   framing and avoids the platform ever looking like it auto-files anything.
5. **Dev 1, ~1–2 h — wire triggers.** Auto-open on a live session ending in
   SUSPICIOUS/SCAM; a "Prepare Report" button in the DANGER coach banner;
   a per-history-entry "Report" action (GET existing draft, or generate one
   if none exists yet).
6. **Optional, ~1–2 h** — same SHA-256 integrity hash + print/PDF stylesheet
   idea as Plan A, but now hashing the (possibly user-edited) final text,
   which is the more honest place for an "auditability" claim to live.

**Total: ~2–2.5 days across all three devs** — Dev 3 and Dev 1 both
meaningfully committed; less time left for Tier 1 roadmap items.

---

## Comparison

| | Plan A (static) | Plan B (LLM + modal) |
|---|---|---|
| Effort | ~1 day, Dev 1 (+ shared 3–4h Dev 2) | ~2–2.5 days, all 3 devs |
| New backend surface | None | `report.py`, `report_generator.py`, `ReportDraft` schema |
| API/quota cost | Zero | 1 Groq call per generate/regenerate (cheap, but non-zero) |
| Hallucination risk | None — pure template | Bounded by design (LLM sees only pre-verified facts, writes 1 paragraph) |
| Editable before filing | No | Yes |
| Works fully offline | Always | Always (template fallback), but LLM version needs a key for the polished paragraph |
| Judging fit | Closes the PS's "guided reporting" gap adequately now | Same gap, plus stronger "legal admissibility" / "auditability" talking points (Evaluation Focus bullet) |

## Recommendation

Ship **Plan A now** — it already closes the PS gap, costs nothing, and frees
Dev 1/Dev 3 time for `HACKATHON_ALIGNMENT_ROADMAP.md` Tier 1 items (digital-
arrest category naming, message-checker tab, number reputation), which score
against more judging-weight categories per hour than polishing a report that
already works. Treat **Plan B as a Tier 2 stretch item** — worth doing only
if Tier 0/1 are green with time to spare, since "editable, LLM-authored,
persisted report" is a real upgrade but a narrower one than the roadmap's
other medium-lift items.
