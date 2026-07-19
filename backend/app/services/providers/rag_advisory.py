from fastapi.concurrency import run_in_threadpool
from app.services.evidence_provider import EvidenceProvider, Evidence
from app.rag.query_engine import RAGQueryEngine

class RAGAdvisoryProvider(EvidenceProvider):
    """
    Evidence provider that queries the ChromaDB local vector store for regulatory
    advisories matching the current call transcript.
    """
    
    @property
    def name(self) -> str:
        return "rag_match"

    async def evaluate(self, context: dict) -> Evidence:
        session = context.get("session")
        transcript = context.get("transcript", "")
        
        advisories = []
        if session is not None and getattr(session, "llm_advisories", None):
            advisories = session.llm_advisories
            
        # Query database directly if no cached advisories exist (e.g. initial phase or batch path)
        if not advisories and transcript.strip():
            try:
                advisories = await run_in_threadpool(
                    RAGQueryEngine.query_advisories,
                    transcript,
                    2
                )
            except Exception as e:
                print(f"Error querying advisories in RAGAdvisoryProvider: {e}")

        count = len(advisories)
        # 1 advisory = 0.5 score, 2+ advisories = 1.0 score
        score = min(1.0, count * 0.5)
        
        explanation = "No matching regulatory warning advisories found."
        if count > 0:
            titles = [adv.title for adv in advisories]
            explanation = f"Matched {count} official scam advisory: {', '.join(titles)}."

        return Evidence(
            source=self.name,
            score=score,
            confidence=1.0 if transcript.strip() else 0.0,
            weight=0.10,
            details={
                "count": count,
                "advisory_titles": [adv.title for adv in advisories]
            },
            explanation=explanation
        )
