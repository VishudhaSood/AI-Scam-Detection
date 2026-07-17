from datetime import datetime
from app.models.schemas import AnalysisResponse
from app.rag.query_engine import RAGQueryEngine

class AnalyzerService:
    """
    Service containing the core analysis business logic.
    Updated in Milestone 3 to delegate call evaluations to the RAG Query Engine
    (retrieves advisories from ChromaDB + analyzes via Qwen LLM on OpenRouter).
    """

    @staticmethod
    def analyze_transcript(text: str) -> AnalysisResponse:
        # 1. Trigger the RAG + OpenRouter LLM pipeline
        result = RAGQueryEngine.evaluate_transcript(text)

        # 2. Package and return the structured response
        return AnalysisResponse(
            transcript=text,
            risk_score=result["risk_score"],
            label=result["label"],
            scam_category=result["scam_category"],
            deepfake_probability=result.get("deepfake_probability", 0.05),
            explanation=result["explanation"],
            advisories=result["advisories"],
            analyzed_at=datetime.utcnow()
        )
