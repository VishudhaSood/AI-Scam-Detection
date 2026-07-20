import os
import json
import logging
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

from app.rag.vector_store import VectorStoreManager
from app.models.schemas import Advisory

# Load environment variables
load_dotenv()

logger = logging.getLogger("app.rag")


def _get_llm_client():
    """
    Returns (client, model_name) using the first available LLM provider.
    Priority: GROQ_API_KEY > OPENROUTER_API_KEY > None (fallback).
    """
    # --- Option 1: Groq (recommended, free, fast) ---
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key and "your_groq" not in groq_key.lower():
        model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
        )
        logger.info(f"LLM provider: Groq ({model})")
        return client, model

    # --- Option 2: OpenRouter ---
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key and "your_openrouter" not in openrouter_key.lower():
        model = os.environ.get("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
            default_headers={
                "HTTP-Referer": "https://github.com/VishudhaSood/AI-Scam-Detection",
                "X-Title": "AI Scam Guard Platform"
            }
        )
        logger.info(f"LLM provider: OpenRouter ({model})")
        return client, model

    # --- No key configured ---
    return None, None


class RAGQueryEngine:
    """
    Query Engine coordinating RAG search in ChromaDB and LLM analysis via Groq/OpenRouter.
    Optimized to run in a single LLM API query request.
    """

    @classmethod
    def query_advisories(cls, transcript: str, n_results: int = 2) -> List[Advisory]:
        """
        Performs semantic similarity search inside ChromaDB collection
        to retrieve the most relevant regulatory advisories.
        """
        try:
            collection = VectorStoreManager.get_collection()
            
            if collection.count() == 0:
                logger.warning("ChromaDB collection is empty. Run index_docs.py first.")
                return []
                
            results = collection.query(
                query_texts=[transcript],
                n_results=n_results
            )
            
            advisories = []
            if results and "metadatas" in results and results["metadatas"]:
                metadata_list = results["metadatas"][0]
                distances = results.get("distances", [[]])[0] if "distances" in results and results["distances"] else []
                
                for i, meta in enumerate(metadata_list):
                    dist = distances[i] if i < len(distances) else 0.0
                    
                    # Threshold check: ignore documents with distance > 1.25 (weak match)
                    if dist <= 1.25:
                        advisories.append(Advisory(
                            title=meta.get("title", "Unknown Advisory"),
                            source=meta.get("source", "Unknown"),
                            description=meta.get("description", "No details available."),
                            url=meta.get("url", None)
                        ))
            return advisories
        except Exception as e:
            logger.error(f"Error querying ChromaDB vector store: {e}")
            return []

    @classmethod
    def evaluate_transcript(cls, transcript: str) -> Dict[str, Any]:
        """
        Retrieves matching context warnings and prompts the LLM to evaluate.
        """
        # 1. Retrieve RAG advisories
        advisories = cls.query_advisories(transcript, n_results=2)
        
        # Format context
        context_str = ""
        for i, adv in enumerate(advisories):
            context_str += f"\nAdvisory {i+1} [{adv.source}]: {adv.title}\nDescription: {adv.description}\n"

        # 2. Get LLM client (Groq or OpenRouter)
        client, model_name = _get_llm_client()

        if client is None:
            logger.warning("No LLM API key configured in .env. Running local keyword fallback.")
            return cls._get_fallback_mock(transcript, advisories)

        system_prompt = (
            "You are an AI Scam Auditor specializing in Indian phone scams. Your task is to analyze the phone call transcript for fraud, phishing, or financial scam markers.\n"
            "Evaluate whether the conversation details match any warning patterns in the provided official regulatory advisories.\n\n"
            "### CRITICAL: NEGATION & CONTEXT AWARENESS\n"
            "Pay careful attention to WHO is speaking and WHAT they are saying:\n"
            "- 'do not share your OTP' is a SAFETY WARNING, not a scam.\n"
            "- 'never give your password' is protective advice, not a threat.\n"
            "- 'my bank called me back, everything is fine' is a benign statement.\n"
            "- Only flag as SCAM when the CALLER is DEMANDING credentials, money, or threatening the listener.\n\n"
            "### SCAM CATEGORIES TO DETECT:\n"
            "- Digital Arrest / Law Enforcement Impersonation: Scammer poses as CBI, Police, Customs, or Narcotics officer. Threatens arrest via video call. Demands 'settlement fee'.\n"
            "- Bank Impersonation (KYC/OTP): Scammer poses as bank manager. Claims account is blocked. Demands OTP, PIN, or CVV.\n"
            "- Lottery & Prize Scam: Claims victim won lottery/KBC prize. Demands processing fee.\n"
            "- Tech Support Scam: Claims computer is infected. Demands AnyDesk/TeamViewer access.\n"
            "- Loan App Fraud: Unauthorized lending apps with hidden fees and aggressive recovery.\n\n"
            "### REGULATORY ADVISORIES CONTEXT:\n"
            f"{context_str or 'No relevant advisories found.'}\n\n"
            "### OUTPUT FORMAT INSTRUCTIONS:\n"
            "You must return your analysis strictly in raw JSON format. No markdown fences, no wrapping, no conversational prefix.\n"
            "The JSON must contain exactly these keys:\n"
            "{\n"
            '  "risk_score": <float between 0.0 and 1.0 representing threat level>,\n'
            '  "label": <string, either "SAFE", "SUSPICIOUS", or "SCAM">,\n'
            '  "scam_category": <string, e.g., "Digital Arrest", "Bank Impersonation (KYC)", "Lottery & Prize Scam", or "None">,\n'
            '  "explanation": <string explaining your evaluation and highlighting exact red flags in the transcript>\n'
            "}"
        )

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Audit this call transcript:\n\"\"\"\n{transcript}\n\"\"\""}
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=15.0
            )

            response_text = response.choices[0].message.content.strip()
            result = json.loads(response_text)
            result["advisories"] = advisories
            return result

        except Exception as e:
            logger.error(f"Error during LLM evaluation: {e}")
            return cls._get_fallback_mock(transcript, advisories)

    @classmethod
    def _get_fallback_mock(cls, transcript: str, advisories: List[Advisory]) -> Dict[str, Any]:
        """
        Heuristic fallback if LLM querying fails.
        """
        text_lower = transcript.lower()
        if any(kw in text_lower for kw in ["lottery", "prize", "win", "crore", "lakh"]):
            risk_score = 0.90
            label = "SCAM"
            category = "Lottery & Prize Scam"
            explanation = "[FALLBACK MOCK ANALYSIS - NO LIVE LLM] Conversation contains lottery winnings urgency markers. Caller demands processing fees."
        elif any(kw in text_lower for kw in ["otp", "bank", "manager", "kyc", "card blocked"]):
            risk_score = 0.95
            label = "SCAM"
            category = "Bank Impersonation (KYC/OTP)"
            explanation = "[FALLBACK MOCK ANALYSIS - NO LIVE LLM] Urgent demands for banking credentials or KYC updates detected."
        elif any(kw in text_lower for kw in ["police", "cbi", "arrest", "contraband", "digital arrest", "cyber police"]):
            risk_score = 0.93
            label = "SCAM"
            category = "Digital Arrest / Law Enforcement Impersonation"
            explanation = "[FALLBACK MOCK ANALYSIS - NO LIVE LLM] Threats of arrest warrant or customs violation intercepts detected."
        else:
            risk_score = 0.10
            label = "SAFE"
            category = "None"
            explanation = "[FALLBACK MOCK ANALYSIS - NO LIVE LLM] Conversation is evaluated as safe. No urgency signals or known scam triggers."

        return {
            "risk_score": risk_score,
            "label": label,
            "scam_category": category,
            "explanation": explanation,
            "advisories": advisories
        }

    @classmethod
    def evaluate_incremental(cls, transcript: str, prior_questions: List[str] = None) -> Dict[str, Any]:
        """
        Retrieves advisories and prompts the LLM to perform an incremental audit on the live transcript.
        Evaluates risk score, categories, safe actions, suggested questions, and evasion verdict.
        """
        # 1. Retrieve advisories
        advisories = cls.query_advisories(transcript, n_results=2)
        context_str = ""
        for i, adv in enumerate(advisories):
            context_str += f"\nAdvisory {i+1} [{adv.source}]: {adv.title}\nDescription: {adv.description}\n"

        # 2. Get LLM client
        client, model_name = _get_llm_client()

        if client is None:
            return cls._get_fallback_mock_incremental(transcript, prior_questions or [], advisories)

        # 3. Setup API prompt
        prior_str = json.dumps(prior_questions or [])
        system_prompt = (
            "You are an AI Scam Auditor specializing in Indian phone scams. Analyze this live, incomplete, mixed two-speaker transcript.\n"
            "Evaluate whether it matches any warning patterns in the regulatory advisories.\n\n"
            "### CRITICAL: NEGATION & CONTEXT AWARENESS\n"
            "Pay careful attention to WHO is speaking and WHAT they are saying:\n"
            "- 'do not share your OTP' or 'never give OTP' is a SAFETY WARNING from the listener, NOT a scam.\n"
            "- 'my bank confirmed everything is fine' is benign.\n"
            "- Only classify as SUSPICIOUS/SCAM when the CALLER is actively demanding credentials, money, or threatening.\n"
            "- Benign small talk ('hello', 'how are you', 'goodbye') is SAFE with risk 0.05.\n\n"
            "### TRANSCRIPT NOISE GUIDELINE:\n"
            "The transcript is generated in real-time by a local speech-to-text model on a speakerphone conversation.\n"
            "It will contain transcription noise, typos, missing punctuation, and grammatical mistakes.\n"
            "Evaluate the high-level social engineering, coercion, or fraud patterns, NOT the verbatim wording.\n\n"
            "### SCAM CATEGORIES TO DETECT:\n"
            "- Digital Arrest / Law Enforcement Impersonation: CBI, Police, Customs, Narcotics officer impersonation. Video call 'arrest'. Settlement fee demands.\n"
            "- Bank Impersonation (KYC/OTP): Fake bank manager. Account blocked threats. OTP/PIN/CVV demands.\n"
            "- Lottery & Prize Scam: KBC/lottery wins. Processing fee demands.\n"
            "- Tech Support Scam: Fake Microsoft/antivirus. AnyDesk/TeamViewer demands.\n\n"
            "### REGULATORY ADVISORIES CONTEXT:\n"
            f"{context_str or 'No relevant advisories found.'}\n\n"
            "### RECENTLY SUGGESTED VERIFICATION QUESTIONS:\n"
            f"{prior_str}\n\n"
            "### VERIFICATION QUESTION GENERATION RULES:\n"
            "If the conversation matches a SUSPICIOUS classification, you may suggest up to 3 identity-verification questions for the user to ask the caller.\n"
            "Rules for questions:\n"
            "- They must be exit-oriented (e.g. ask for official ID and state they will hang up and call the official organization back).\n"
            "- They must NEVER suggest baiting, mock interactions, or prolonging the scammer's call.\n"
            "- If the conversation is SAFE or already confirmed as a SCAM, do not suggest questions.\n\n"
            "### QUESTION-RESPONSE VERDICT GUIDELINES:\n"
            "Analyze the tail of the transcript to check how the caller reacted to any previously suggested questions (listed under RECENTLY SUGGESTED VERIFICATION QUESTIONS).\n"
            "Classify the caller's reaction into exactly one of these labels:\n"
            "- \"EVASIVE\": Caller avoided answering, changed the subject, or responded with vague/suspicious excuses.\n"
            "- \"REFUSED\": Caller directly refused to answer or verify their identity.\n"
            "- \"THREATENED\": Caller responded with hostility, anger, threats of arrest, fines, or account blockages.\n"
            "- \"PLAUSIBLE\": Caller answered the questions cooperatively and logically (e.g. agreed to send an official verification email).\n"
            "- \"NOT_YET_ANSWERED\": The questions have not been asked by the user, or the caller has not yet responded in the transcript.\n"
            "- \"N/A\": No questions have been suggested yet.\n\n"
            "### OUTPUT FORMAT INSTRUCTIONS:\n"
            "You must return your analysis strictly in raw JSON format. No markdown fences. Keys:\n"
            "{\n"
            '  "risk_score": <float between 0.0 and 1.0 representing threat level>,\n'
            '  "label": <"SAFE" | "SUSPICIOUS" | "SCAM">,\n'
            '  "scam_category": <string matching the category name, or "None">,\n'
            '  "explanation": <string explaining the reasoning>,\n'
            '  "red_flags": [<string red flag indicators detected in the text>],\n'
            '  "suggested_questions": [<list of strings, max 3, verification questions only>],\n'
            '  "safe_actions": [<list of strings, defensive guidance for user safety when threat is high>],\n'
            '  "question_response_verdict": <"EVASIVE" | "REFUSED" | "THREATENED" | "PLAUSIBLE" | "NOT_YET_ANSWERED" | "N/A">\n'
            "}"
        )

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Audit this live transcript:\n\"\"\"\n{transcript}\n\"\"\""}
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=15.0
            )
            response_text = response.choices[0].message.content.strip()
            result = json.loads(response_text)
            result["advisories"] = advisories
            return result
        except Exception as e:
            logger.error(f"Error in evaluate_incremental LLM: {e}")
            return cls._get_fallback_mock_incremental(transcript, prior_questions or [], advisories)

    @classmethod
    def _get_fallback_mock_incremental(cls, transcript: str, prior_questions: List[str], advisories: List[Advisory]) -> Dict[str, Any]:
        """
        Milestone 8 Incremental Heuristic Fallback
        """
        text_lower = transcript.lower()
        risk_score = 0.10
        label = "SAFE"
        category = "None"
        explanation = "[FALLBACK MOCK ANALYSIS - NO LIVE LLM] Conversation appears normal. No scam indicators detected."
        red_flags = []
        suggested_questions = []
        safe_actions = []
        verdict = "N/A"

        # Determine scam match
        is_scam = False
        if any(kw in text_lower for kw in ["lottery", "prize", "win", "crore", "lakh"]):
            risk_score = 0.60
            label = "SUSPICIOUS"
            category = "Lottery & Prize Scam"
            explanation = "[FALLBACK MOCK ANALYSIS - NO LIVE LLM] Urgent demands or congratulatory announcements of winnings."
            red_flags = ["Lottery winnings announced", "Advance fee processing demand"]
            suggested_questions = [
                "Ask which official website registry lists your ticket number.",
                "Say you will only verify the prize via the official government portal."
            ]
            is_scam = True
        elif any(kw in text_lower for kw in ["otp", "bank", "manager", "kyc", "card blocked"]):
            risk_score = 0.70
            label = "SUSPICIOUS"
            category = "Bank Impersonation (KYC)"
            explanation = "[FALLBACK MOCK ANALYSIS - NO LIVE LLM] Suspicious card blockage warning or OTP request."
            red_flags = ["Demanded credentials or OTP", "KYC update urgency"]
            suggested_questions = [
                "Ask for their employee ID and main branch department name.",
                "Tell them you will hang up and call the official customer care number on your card."
            ]
            is_scam = True
        elif any(kw in text_lower for kw in ["police", "cbi", "arrest", "contraband", "warrant", "digital arrest", "cyber police"]):
            risk_score = 0.72
            label = "SUSPICIOUS"
            category = "Digital Arrest / Law Enforcement Impersonation"
            explanation = "[FALLBACK MOCK ANALYSIS - NO LIVE LLM] Threats of arrest warrant or customs violation intercepts."
            red_flags = ["Arrest warrant threats", "Coercion into secrecy"]
            suggested_questions = [
                "Ask which official police station is issuing this warrant and their ID.",
                "Say you will call back the main police control room to verify their identity."
            ]
            is_scam = True

        if is_scam:
            # Check for evasion/refusal in transcript tail
            # If the user has prior questions and the scammer refuses/threatens
            if prior_questions:
                if any(kw in text_lower for kw in ["no", "why", "refuse", "not telling", "don't ask", "shut up", "don't tell"]):
                    verdict = "EVASIVE"
                    risk_score = round(min(0.98, risk_score + 0.20), 2)
                    label = "SCAM"
                    safe_actions = ["Do NOT share any OTP code.", "Do NOT transfer any processing fees.", "Hang up the call immediately."]
                    suggested_questions = [] # Clear questions in DANGER
                else:
                    verdict = "NOT_YET_ANSWERED"
            else:
                verdict = "NOT_YET_ANSWERED"

        return {
            "risk_score": risk_score,
            "label": label,
            "scam_category": category,
            "explanation": explanation,
            "red_flags": red_flags,
            "suggested_questions": suggested_questions,
            "safe_actions": safe_actions,
            "question_response_verdict": verdict,
            "advisories": advisories
        }
