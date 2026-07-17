from pydantic import BaseModel
from typing import List

class HeuristicResult(BaseModel):
    risk: float
    tier_hits: List[str]
    trigger_llm: bool

class HeuristicScorer:
    """
    Stub implementation of HeuristicScorer.
    Developer 3 will implement the full keyword-based scoring rules.
    """
    @staticmethod
    def score(text: str) -> HeuristicResult:
        text_lower = text.lower()
        # Basic stub logic for Milestone 7 testing
        tier_hits = []
        trigger_llm = False
        risk = 0.1

        if any(kw in text_lower for kw in ["otp", "pin", "cvv", "arrest", "anydesk", "teamviewer"]):
            risk = 0.9
            tier_hits.append("critical_threat_keyword")
            trigger_llm = True
        elif any(kw in text_lower for kw in ["kyc", "card blocked", "lottery", "prize", "police", "cbi"]):
            risk = 0.6
            tier_hits.append("suspicious_keyword")
        elif any(kw in text_lower for kw in ["urgent", "secret"]):
            risk = 0.3
            tier_hits.append("urgency_signal")

        return HeuristicResult(
            risk=risk,
            tier_hits=tier_hits,
            trigger_llm=trigger_llm
        )
