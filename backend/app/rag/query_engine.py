import os
import json
import logging
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

from app.rag.vector_store import VectorStoreManager
from app.models.schemas import Advisory, AnalysisResponse

# Load environment variables
load_dotenv()

logger = logging.getLogger("app.rag")

class RAGQueryEngine:
    """
    Query Engine coordinating RAG search in ChromaDB and Qwen-LLM analysis via OpenRouter.
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
                for meta in metadata_list:
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
        Retrieves matching context warnings and prompts Qwen to evaluate.
        """
        # 1. Retrieve RAG advisories
        advisories = cls.query_advisories(transcript, n_results=2)
        
        # Format context
        context_str = ""
        for i, adv in enumerate(advisories):
            context_str += f"\nAdvisory {i+1} [{adv.source}]: {adv.title}\nDescription: {adv.description}\n"

        # 2. Check for OpenRouter configuration
        api_key = os.environ.get("OPENROUTER_API_KEY")
        model_name = os.environ.get("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")

        if not api_key or "your_openrouter" in api_key.lower():
            logger.warning("OPENROUTER_API_KEY is not configured in .env. Running local fallback.")
            return cls._get_fallback_mock(transcript, advisories)

        # 3. Initialize OpenRouter client
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/VishudhaSood/AI-Scam-Detection",
                "X-Title": "AI Scam Guard Platform"
            }
        )

        system_prompt = (
            "You are an AI Scam Auditor. Your task is to analyze the phone call transcript for fraud, phishing, or financial scam markers.\n"
            "Evaluate whether the conversation details match any warning patterns in the provided official regulatory advisories.\n\n"
            "### REGULATORY ADVISORIES CONTEXT:\n"
            f"{context_str or 'No relevant advisories found.'}\n\n"
            "### OUTPUT FORMAT INSTRUCTIONS:\n"
            "You must return your analysis strictly in raw JSON format. No markdown fences, no wrapping, no conversational prefix.\n"
            "The JSON must contain exactly these keys:\n"
            "{\n"
            '  "risk_score": <float between 0.0 and 1.0 representing threat level>,\n'
            '  "label": <string, either "SAFE", "SUSPICIOUS", or "SCAM">,\n'
            '  "scam_category": <string, e.g., "Lottery & Prize Scam", "Bank Impersonation (KYC)", "Law Enforcement Impersonation", or "None">,\n'
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
                temperature=0.1
            )

            response_text = response.choices[0].message.content.strip()
            
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                response_text = "\n".join(lines).strip()

            result = json.loads(response_text)
            result["advisories"] = advisories
            return result

        except Exception as e:
            logger.error(f"Error during OpenRouter evaluation: {e}")
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
            explanation = "Conversation contains lottery winnings urgency markers. Caller demands processing fees. (Fallback Analysis)"
        elif any(kw in text_lower for kw in ["otp", "bank", "manager", "kyc", "card blocked"]):
            risk_score = 0.95
            label = "SCAM"
            category = "Bank Impersonation (KYC/OTP)"
            explanation = "Urgent demands for banking credentials or KYC updates detected. (Fallback Analysis)"
        elif any(kw in text_lower for kw in ["police", "cbi", "arrest", "contraband"]):
            risk_score = 0.93
            label = "SCAM"
            category = "Impersonation of Law Enforcement"
            explanation = "Threats of arrest related to illegal packages or police warrants. (Fallback Analysis)"
        else:
            risk_score = 0.10
            label = "SAFE"
            category = "None"
            explanation = "Conversation is evaluated as safe. No urgency signals or known scam triggers. (Fallback Analysis)"

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
        Retrieves advisories and prompts Qwen to perform an incremental audit on the live transcript.
        Evaluates risk score, categories, safe actions, suggested questions, and evasion verdict.
        """
        # 1. Retrieve advisories
        advisories = cls.query_advisories(transcript, n_results=2)
        context_str = ""
        for i, adv in enumerate(advisories):
            context_str += f"\nAdvisory {i+1} [{adv.source}]: {adv.title}\nDescription: {adv.description}\n"

        # 2. Check OpenRouter configuration
        api_key = os.environ.get("OPENROUTER_API_KEY")
        model_name = os.environ.get("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")

        if not api_key or "your_openrouter" in api_key.lower():
            return cls._get_fallback_mock_incremental(transcript, prior_questions or [], advisories)

        # 3. Setup OpenRouter API prompt
        prior_str = json.dumps(prior_questions or [])
        system_prompt = (
            "You are an AI Scam Auditor. Analyze this live, incomplete, mixed two-speaker transcript.\n"
            "Evaluate whether it matches any patterns in the regulatory advisories.\n\n"
            "### REGULATORY ADVISORIES CONTEXT:\n"
            f"{context_str or 'No relevant advisories found.'}\n\n"
            "### RECENTLY SUGGESTED VERIFICATION QUESTIONS:\n"
            f"{prior_str}\n\n"
            "### OUTPUT FORMAT INSTRUCTIONS:\n"
            "You must return your analysis strictly in raw JSON format. No markdown fences. Keys:\n"
            "{\n"
            '  "risk_score": <float between 0.0 and 1.0 representing threat level>,\n'
            '  "label": <"SAFE" | "SUSPICIOUS" | "SCAM">,\n'
            '  "scam_category": <string>,\n'
            '  "explanation": <string>,\n'
            '  "red_flags": [<string red flag chips detected in transcript>],\n'
            '  "suggested_questions": [<string suggested identity-verification questions for the user to ask the caller, max 3. Only if risk is medium. exit-oriented like calling official number back, written notice from official email. Never bait.>],\n'
            '  "safe_actions": [<string actions for user safety, e.g. Do NOT share OTP, Do NOT install remote control apps. Only if risk is high.>],\n'
            '  "question_response_verdict": <"EVASIVE" | "REFUSED" | "THREATENED" | "PLAUSIBLE" | "NOT_YET_ANSWERED" | "N/A">\n'
            "}"
        )

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/VishudhaSood/AI-Scam-Detection",
                "X-Title": "AI Scam Guard Platform"
            }
        )

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Audit this live transcript:\n\"\"\"\n{transcript}\n\"\"\""}
                ],
                temperature=0.1
            )
            response_text = response.choices[0].message.content.strip()
            
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                response_text = "\n".join(lines).strip()

            result = json.loads(response_text)
            result["advisories"] = advisories
            return result
        except Exception as e:
            logger.error(f"Error in evaluate_incremental OpenRouter: {e}")
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
        explanation = "Conversation appears normal. No scam indicators detected. (Fallback)"
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
            explanation = "Urgent demands or congratulatory announcements of winnings. (Fallback)"
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
            explanation = "Suspicious card blockage warning or OTP request. (Fallback)"
            red_flags = ["Demanded credentials or OTP", "KYC update urgency"]
            suggested_questions = [
                "Ask for their employee ID and main branch department name.",
                "Tell them you will hang up and call the official customer care number on your card."
            ]
            is_scam = True
        elif any(kw in text_lower for kw in ["police", "cbi", "arrest", "contraband", "warrant"]):
            risk_score = 0.72
            label = "SUSPICIOUS"
            category = "Law Enforcement Impersonation"
            explanation = "Threats of arrest warrant or custom violation intercepts. (Fallback)"
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
                    risk_score = min(0.98, risk_score + 0.20)
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
