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

        # A word or two of noise ("Police!") can legitimately sit near an advisory
        # embedding and instantly score 100% here. Require a minimal utterance
        # before advisory matches count as evidence.
        if len(transcript.split()) < 5:
            return Evidence(
                source=self.name,
                score=0.0,
                confidence=0.0,
                weight=0.10,
                details={"count": 0, "advisory_titles": []},
                explanation="Transcript too short for advisory matching."
            )

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

        # Advisories are corroborating evidence, not a standalone signal: the
        # vector store always returns nearest neighbours (and the fallback DB's
        # distance scale defeats the threshold filter), so benign small talk can
        # "match" advisories. Only count them when the transcript itself shows
        # scam content via keywords or the LLM audit.
        if score > 0.0:
            from app.services.heuristic_scorer import HeuristicScorer
            content_risk = HeuristicScorer.score(transcript).risk
            llm_risk = getattr(session, "last_llm_risk", 0.0) if session is not None else 0.0
            if content_risk < 0.2 and llm_risk < 0.4:
                score = 0.0
                explanation = (f"{count} nearby advisories retrieved but no corroborating "
                               "scam signals in the transcript; not counted as evidence.")

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
