from app.services.evidence_provider import EvidenceProvider, Evidence
from app.services.heuristic_scorer import HeuristicScorer

class HeuristicScorerProvider(EvidenceProvider):
    """
    Evidence provider that performs fast regex keyword scanning across three tiers.
    """
    
    @property
    def name(self) -> str:
        return "heuristics"

    async def evaluate(self, context: dict) -> Evidence:
        transcript = context.get("transcript", "")
        heuristic_result = HeuristicScorer.score(transcript)
        
        explanation = "No suspicious keywords detected."
        if heuristic_result.tier_hits:
            explanation = f"Keyword scanner matched scam patterns: {', '.join(heuristic_result.tier_hits)}."

        return Evidence(
            source=self.name,
            score=heuristic_result.risk,
            confidence=1.0 if transcript.strip() else 0.0,
            weight=0.25,
            details={
                "tier_hits": heuristic_result.tier_hits,
                "trigger_llm": heuristic_result.trigger_llm
            },
            explanation=explanation
        )
