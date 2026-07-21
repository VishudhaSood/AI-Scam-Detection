import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger("app.services.report_generator")


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
        
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # 1. Fact-constrained prompt assembly
        fact_bullets = (
            f"- Date & Time: {now_str}\n"
            f"- Caller Phone Number: {caller_number if caller_number else 'Not Provided'}\n"
            f"- Threat Evaluation Label: {label} (Risk Score: {int(round(risk_score * 100))}%)\n"
            f"- Scam Category: {scam_category}\n"
            f"- Overall Evidence Confidence: {int(round(confidence * 100))}% \n"
            f"- Incident Explanation: {explanation}\n"
            f"- Transcript Excerpt: \"{transcript[:300]}\"\n"
        )
        if advisories:
            adv_titles = ", ".join([a.get("title", "") for a in advisories if isinstance(a, dict)])
            fact_bullets += f"- Matched Advisories: {adv_titles}\n"

        # 2. Call Groq LLM for 2-sentence formal executive summary
        executive_summary = await cls._generate_llm_summary(fact_bullets, label, scam_category, risk_score, now_str)

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

        full_report_text = f"""======================================================================
INCIDENT AUDIT REPORT & CYBERCRIME COMPLAINT DRAFT
National Cyber Crime Reporting Portal (cybercrime.gov.in) / Helpline 1930
======================================================================

Date & Time: {now_str}
Threat Evaluation Label: {label} (Risk Score: {int(round(risk_score * 100))}%)
Detected Scam Category: {scam_category}
Caller Phone Number: {caller_number if caller_number else 'Not Provided'}
Overall Evidence Confidence: {int(round(confidence * 100))}%

----------------------------------------------------------------------
EXECUTIVE SUMMARY
----------------------------------------------------------------------
{executive_summary}

----------------------------------------------------------------------
INCIDENT TRANSCRIPT EXCERPT
----------------------------------------------------------------------
"{transcript}"

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
======================================================================"""

        # 4. Compute SHA-256 audit hash
        sha256_hash = hashlib.sha256(full_report_text.encode("utf-8")).hexdigest()

        return {
            "executive_summary": executive_summary,
            "report_text": full_report_text,
            "sha256_hash": sha256_hash
        }

    @classmethod
    async def _generate_llm_summary(cls, fact_bullets: str, label: str, scam_category: str, risk_score: float, now_str: str) -> str:
        """
        Calls Groq/OpenRouter via query_engine's client resolver to write a formal 2-sentence summary.
        Falls back to a deterministic template if API call fails or times out.
        """
        fallback_summary = (
            f"On {now_str}, an incoming phone call was audited by AI Scam Detection and classified as {label} "
            f"with a risk score of {int(round(risk_score * 100))}%. The call exhibited characteristics matching "
            f"{scam_category} scam patterns."
        )

        try:
            from app.rag.query_engine import _get_llm_client
            client, model = _get_llm_client()

            system_prompt = (
                "You are an expert legal cybercrime incident reporting assistant. "
                "Your task is to write a concise, formal 2-sentence incident executive summary for a "
                "Cybercrime Helpline (1930) complaint report based strictly on the provided bulleted facts. "
                "CRITICAL: Do NOT invent any names, amounts, dates, or details not present in the bullet list."
            )

            prompt = f"FACT BULLETS:\n{fact_bullets}\n\nWrite a formal 2-sentence executive summary:"

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=150,
                timeout=8.0
            )

            result = response.choices[0].message.content.strip()
            return result if result else fallback_summary

        except Exception as e:
            logger.warning(f"Failed to generate LLM executive summary, using fallback: {e}")
            return fallback_summary
