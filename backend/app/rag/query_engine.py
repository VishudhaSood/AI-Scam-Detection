import os
import json
import logging
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

from app.rag.vector_store import VectorStoreManager
from app.models.schemas import Advisory, AnalysisResponse

# Load environment variables from backend/.env
load_dotenv()

logger = logging.getLogger("app.rag")

class RAGQueryEngine:
    """
    Query Engine coordinating RAG search in ChromaDB and Qwen-LLM analysis via OpenRouter.
    """

    @classmethod
    def query_advisories(cls, transcript: str, n_results: int = 2) -> List[Advisory]:
        """
        Performs semantic similarity search inside ChromaDB collection
        to retrieve the most relevant regulatory advisories.
        """
        try:
            collection = VectorStoreManager.get_collection()
            
            # If the database is empty, return no advisories
            if collection.count() == 0:
                logger.warning("ChromaDB collection is empty. Run index_docs.py first.")
                return []
                
            results = collection.query(
                query_texts=[transcript],
                n_results=n_results
            )
            
            advisories = []
            if results and "metadatas" in results and results["metadatas"]:
                # Parse list of dictionaries returned by Chroma DB
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
        Performs a full scam evaluation. Retrieves relevant context from vector database
        and prompts Qwen (via OpenRouter) to audit the conversation.
        """
        # 1. Retrieve RAG advisories
        advisories = cls.query_advisories(transcript, n_results=2)
        
        # Format the advisories as context for the model prompt
        context_str = ""
        for i, adv in enumerate(advisories):
            context_str += f"\nAdvisory {i+1} [{adv.source}]: {adv.title}\nDescription: {adv.description}\n"

        # 2. Check for OpenRouter configuration
        api_key = os.environ.get("OPENROUTER_API_KEY")
        model_name = os.environ.get("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")

        # Graceful fallback in case API key is missing during local setup
        if not api_key or "your_openrouter" in api_key.lower():
            logger.warning("OPENROUTER_API_KEY is not configured in .env. Falling back to dynamic mock logic.")
            # Standard fallback mock analysis to prevent crashes
            return cls._get_fallback_mock(transcript, advisories)

        # 3. Initialize OpenRouter client using the OpenAI SDK
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/VishudhaSood/AI-Scam-Detection",
                "X-Title": "AI Scam Guard Platform"
            }
        )

        # Construct system instructions
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
                temperature=0.1  # Low temperature for deterministic classification
            )

            response_text = response.choices[0].message.content.strip()
            
            # Clean up potential markdown code block backticks if Qwen outputs them
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                response_text = "\n".join(lines).strip()

            result = json.loads(response_text)
            
            # Add retrieved advisories list to the final output dict
            result["advisories"] = advisories
            return result

        except Exception as e:
            logger.error(f"Error during OpenRouter API evaluation: {e}")
            # Fallback on exceptions (e.g. rate limit, context overflow, invalid response syntax)
            return cls._get_fallback_mock(transcript, advisories)

    @classmethod
    def _get_fallback_mock(cls, transcript: str, advisories: List[Advisory]) -> Dict[str, Any]:
        """
        Helper fallback logic that returns keyword-based heuristics if the LLM fails or is unconfigured.
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
