import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List

from fastapi.concurrency import run_in_threadpool

# Imported at module scope, not inside the request handler: resolving this
# import pulls in the OpenAI SDK and the vector store and costs ~2s the first
# time, which would otherwise block the event loop on the first report request.
from app.rag.query_engine import _get_llm_client

logger = logging.getLogger("app.services.report_generator")


def _format_timestamp(value: Any) -> str | None:
    """
    Renders an incident timestamp for the report. Accepts a datetime or the
    ISO-8601 string the frontend sends back through JSON. Returns None when the
    value is missing or unparseable, so the caller can decide on a fallback.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        # Python < 3.11 can't parse a trailing 'Z', which JS toISOString() emits
        cleaned = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        logger.warning("Unparseable incident timestamp %r; falling back to now.", value)
        return None


def _format_duration(seconds: Any) -> str | None:
    """Renders call duration as e.g. '3m 12s'. None when not measured."""
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return f"{total // 60}m {total % 60}s" if total >= 60 else f"{total}s"


class ReportGenerator:
    """
    Service responsible for authoring fact-constrained cybercrime complaint reports.
    Uses Groq (llama-3.3-70b-versatile) to write a formal 2-sentence executive summary
    strictly based on pre-verified fact bullets, then computes a SHA-256 audit hash.
    """

    @classmethod
    async def generate_report(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assembles verified facts, calls Groq for a 2-sentence executive summary,
        and returns the full complaint draft and cryptographic SHA-256 hash.
        """
        transcript = data.get("transcript", "(no speech captured)")
        risk_score = data.get("risk_score", 0.0)
        label = data.get("label", "SUSPICIOUS")
        scam_category = data.get("scam_category", "None")
        confidence = data.get("overall_confidence", 0.0)
        explanation = data.get("explanation", "")
        caller_number = data.get("caller_number", "Not Provided")
        duration_s = data.get("duration_s", 0.0)
        
        advisories: List[Dict[str, Any]] = data.get("advisories", [])
        reasoning_trace: List[str] = data.get("reasoning_trace", [])
        red_flags: List[str] = data.get("red_flags", [])
        
        peak_risk = data.get("peak_risk")

        # When the call happened, vs. when this document was produced. These are
        # only the same for a report drafted mid-call or right after hang-up — a
        # report opened later from Past Audits must still carry the date police
        # will correlate against bank logs, not today's date.
        generated_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        incident_str = _format_timestamp(data.get("analyzed_at"))
        incident_is_live = incident_str is None
        if incident_is_live:
            # No analyzed_at: the mid-call shortcut, where the call is in progress.
            incident_str = f"{generated_str} (call in progress at time of drafting)"

        duration_str = _format_duration(duration_s)

        # 1. Fact-constrained prompt assembly.
        # Everything the model is allowed to state must appear below. The
        # framing bullet is first so the actors are never ambiguous.
        fact_bullets = (
            f"- Incident type: an unknown caller telephoned the complainant\n"
            f"- Incident date & time: {incident_str}\n"
            f"- Caller Phone Number: {caller_number if caller_number else 'Not Provided'}\n"
            f"- Threat Evaluation Label: {label} (Risk Score: {int(round(risk_score * 100))}%)\n"
            f"- Scam Category: {scam_category}\n"
            f"- Overall Evidence Confidence: {int(round(confidence * 100))}% \n"
            f"- Incident Explanation: {explanation}\n"
            f"- Transcript Excerpt: \"{transcript[:300]}\"\n"
        )
        if duration_str:
            fact_bullets += f"- Call Duration: {duration_str}\n"
        if isinstance(peak_risk, (int, float)):
            fact_bullets += f"- Peak Risk During Call: {int(round(peak_risk * 100))}%\n"
        if red_flags:
            fact_bullets += f"- Red Flags Heard: {', '.join(red_flags)}\n"
        if advisories:
            adv_titles = ", ".join([a.get("title", "") for a in advisories if isinstance(a, dict)])
            fact_bullets += f"- Matched Advisories: {adv_titles}\n"

        # 2. Call Groq LLM for 2-sentence formal executive summary
        executive_summary = await cls._generate_llm_summary(
            fact_bullets, label, scam_category, risk_score, incident_str
        )

        # 3. Assemble full complaint document text
        advisories_text = "None matched."
        if advisories:
            formatted_adv = []
            for a in advisories:
                if isinstance(a, dict):
                    title = a.get("title", "Advisory")
                    source = a.get("source", "Official")
                    desc = a.get("description", "")
                    url = a.get("url", "")
                    formatted_adv.append(f"- [{source}] {title}\n  Details: {desc}\n  Reference: {url}")
            advisories_text = "\n\n".join(formatted_adv)

        reasoning_text = "None recorded."
        if reasoning_trace:
            reasoning_text = "\n".join([f"- {step}" for step in reasoning_trace])

        red_flags_text = "None detected."
        if red_flags:
            red_flags_text = "\n".join([f"- {flag}" for flag in red_flags])

        # Optional header lines: only present when the live pipeline measured them
        # (batch/text analyses have no duration or score timeline).
        call_metrics = ""
        if duration_str:
            call_metrics += f"Call Duration: {duration_str}\n"
        if isinstance(peak_risk, (int, float)):
            peak_pct = int(round(peak_risk * 100))
            final_pct = int(round(risk_score * 100))
            # A call that spiked to DANGER and settled lower still reached DANGER;
            # the final score alone hides that, so show both when they differ.
            suffix = f" (final: {final_pct}%)" if peak_pct != final_pct else ""
            call_metrics += f"Peak Risk During Call: {peak_pct}%{suffix}\n"

        # Stated explicitly rather than omitted: a complaint that is silent on voice
        # authenticity could be read as an implicit finding. Voice-spoof detection is
        # not part of the pipeline, so the honest value is "not checked".
        deepfake_probability = data.get("deepfake_probability")
        if isinstance(deepfake_probability, (int, float)):
            voice_line = f"{int(round(deepfake_probability * 100))}% likelihood of synthetic voice"
        else:
            voice_line = "Not checked - automated voice-spoof detection was not applied to this call"

        full_report_text = f"""======================================================================
INCIDENT AUDIT REPORT & CYBERCRIME COMPLAINT DRAFT
National Cyber Crime Reporting Portal (cybercrime.gov.in) / Helpline 1930
======================================================================

Incident Date & Time: {incident_str}
Report Generated: {generated_str}
Threat Evaluation Label: {label} (Risk Score: {int(round(risk_score * 100))}%)
Detected Scam Category: {scam_category}
Caller Phone Number: {caller_number if caller_number else 'Not Provided'}
Overall Evidence Confidence: {int(round(confidence * 100))}%
Voice Authenticity: {voice_line}
{call_metrics}
----------------------------------------------------------------------
EXECUTIVE SUMMARY
----------------------------------------------------------------------
{executive_summary}

----------------------------------------------------------------------
INCIDENT TRANSCRIPT EXCERPT
----------------------------------------------------------------------
"{transcript}"

----------------------------------------------------------------------
DETECTED RED FLAGS & RISK INDICATORS
----------------------------------------------------------------------
{red_flags_text}

----------------------------------------------------------------------
MATCHED REGULATORY ADVISORIES & WARNINGS
----------------------------------------------------------------------
{advisories_text}

----------------------------------------------------------------------
AUDIT REASONING TRACE LOGS
----------------------------------------------------------------------
{reasoning_text}

----------------------------------------------------------------------
OFFICIAL REPORTING HELPLINES & PORTALS
----------------------------------------------------------------------
- Cybercrime Helpline: Call 1930
- Cybercrime Portal: https://cybercrime.gov.in
- Department of Telecommunications (DoT Chakshu): https://sancharsaathi.gov.in/sachet
- RBI Sachet Fraud Portal: https://sachet.rbi.org.in
======================================================================="""

        # 4. Compute SHA-256 audit hash
        sha256_hash = hashlib.sha256(full_report_text.encode("utf-8")).hexdigest()

        return {
            "executive_summary": executive_summary,
            "report_text": full_report_text,
            "sha256_hash": sha256_hash
        }

    @classmethod
    async def _generate_llm_summary(cls, fact_bullets: str, label: str, scam_category: str, risk_score: float, incident_str: str) -> str:
        """
        Calls Groq/OpenRouter via query_engine's client resolver to write a formal 2-sentence summary.
        Falls back to a deterministic template if API call fails or times out.
        """
        fallback_summary = (
            f"On {incident_str}, an incoming phone call was audited by AI Scam Detection and classified as {label} "
            f"with a risk score of {int(round(risk_score * 100))}%. The call exhibited characteristics matching "
            f"{scam_category} scam patterns."
        )

        try:
            client, model = _get_llm_client()

            # The previous prompt named the destination ("for a Cybercrime Helpline
            # (1930) complaint report") inside the task sentence, and the model wove
            # it into the narrative — producing "a caller ... contacted the Cybercrime
            # Helpline", an event that never happened. The document's destination is
            # therefore never mentioned here, and rule 1 states outright that the
            # instructions are not a source of facts.
            system_prompt = (
                "You draft factual incident summaries for fraud audit records.\n\n"
                "TASK: Write exactly two sentences summarising a suspicious phone call, "
                "using only the FACT BULLETS supplied by the user.\n\n"
                "RULES:\n"
                "1. The FACT BULLETS are your only source of information. Nothing in "
                "these instructions is a fact about the incident.\n"
                "2. Describe only what happened during the phone call itself. Do not "
                "state or imply that anyone reported, filed, contacted, or notified any "
                "authority, helpline, portal, bank, or police - no such action has occurred.\n"
                "3. Never invent a name, phone number, amount, date, time, organisation, "
                "or claim that is not written in the FACT BULLETS. If a detail is absent, "
                "omit it rather than guessing.\n"
                "4. The caller is the suspected fraudster; the complainant is the person "
                "who received the call. Do not reverse these roles.\n"
                "5. Write plain formal prose. No headings, bullet points, or preamble - "
                "output the two sentences and nothing else."
            )

            prompt = f"FACT BULLETS:\n{fact_bullets}\n\nWrite the two-sentence summary:"

            # _get_llm_client() returns the SYNCHRONOUS OpenAI client, so this call
            # blocks its thread until Groq answers. Run it off the event loop the
            # same way whisper_reasoning.py does — otherwise the mid-call "Prepare
            # Complaint" button freezes every live WebSocket session for up to 8s.
            response = await run_in_threadpool(
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=150,
                    timeout=8.0
                )
            )

            result = response.choices[0].message.content.strip()
            return result if result else fallback_summary

        except Exception as e:
            logger.warning(f"Failed to generate LLM executive summary, using fallback: {e}")
            return fallback_summary
