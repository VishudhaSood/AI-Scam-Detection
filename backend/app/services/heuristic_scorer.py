import re
from dataclasses import dataclass
from typing import List

@dataclass
class HeuristicResult:
    """
    Data contract output for the Heuristic Scorer module.
    """
    risk: float
    tier_hits: List[str]
    trigger_llm: bool


class HeuristicScorer:
    """
    Scorer service running tiered keyword analyses on conversation text.
    Executes instantly on the CPU, providing raw risk hints for the streaming cycle.
    """

    # Tier 3 (Risk: 0.85 - 0.98): Extreme threat indicators triggering immediate LLM audit
    TIER_3_KEYWORDS = [
        r"\botp\b", r"\bone[- ]time[- ]password\b", r"\bcvv\b", r"\bpin\b", r"\bpassword\b",
        r"\banydesk\b", r"\bteamviewer\b", r"\brustdesk\b", r"\bscreen[- ]share\b", r"\bremote[- ]access\b",
        r"\btransfer[- ]money\b", r"\bsend[- ]money\b", r"\bdeposit[- ]fee\b", r"\bprocessing[- ]fee\b",
        r"\bpayment\b", r"\barrest\b", r"\bwarrant\b", r"\bcbi\b", r"\bpolice[- ]custody\b",
        r"\bcontraband\b", r"\billegal[- ]package\b"
    ]

    # Tier 2 (Risk: 0.50 - 0.74): Medium threat signals of identity fraud and baiting
    TIER_2_KEYWORDS = [
        r"\bkyc\b", r"\bknow[- ]your[- ]customer\b", r"\bupdate[- ]account\b", r"\bsuspend\b",
        r"\bblock\b", r"\bcard[- ]blocked\b", r"\bverification\b", r"\blottery\b", r"\bprize\b",
        r"\blucky[- ]draw\b", r"\bcrore\b", r"\blakh\b", r"\bwin\b", r"\bcustoms\b",
        r"\bfedex\b", r"\bdhl\b", r"\bcourier\b", r"\billegal\b"
    ]

    # Tier 1 (Risk: 0.20 - 0.49): Urgency-building keywords and pressure language
    TIER_1_KEYWORDS = [
        r"\burgent\b", r"\bdo[n']t[- ]tell[- ]anyone\b", r"\bkeep[- ]it[- ]secret\b",
        r"\bconfidential\b", r"\bemergency\b", r"\bcritical\b", r"\bimmediately\b",
        r"\bnow\b", r"\bwithin[- ]1[- ]hour\b"
    ]

    @classmethod
    def score(cls, text: str) -> HeuristicResult:
        """
        Scores the input text block using three-tiered keyword match rules.
        """
        text_lower = text.lower()
        
        # 1. Match Tier 3 (High Threat)
        hits_t3 = []
        for kw in cls.TIER_3_KEYWORDS:
            if re.search(kw, text_lower):
                # Save the cleaned regex word for representation
                hits_t3.append(kw.replace(r"\b", "").replace(r"[- ]", " "))
        
        if hits_t3:
            # Base risk of 0.85, scales up to 0.98 based on quantity of hits
            risk = min(0.98, 0.85 + 0.02 * len(hits_t3))
            return HeuristicResult(
                risk=round(risk, 2),
                tier_hits=hits_t3,
                trigger_llm=True
            )

        # 2. Match Tier 2 (Medium Threat)
        hits_t2 = []
        for kw in cls.TIER_2_KEYWORDS:
            if re.search(kw, text_lower):
                hits_t2.append(kw.replace(r"\b", "").replace(r"[- ]", " "))
        
        if hits_t2:
            # Base risk of 0.50, scales up to 0.74
            risk = min(0.74, 0.50 + 0.04 * len(hits_t2))
            return HeuristicResult(
                risk=round(risk, 2),
                tier_hits=hits_t2,
                trigger_llm=False
            )

        # 3. Match Tier 1 (Low Threat/Urgency)
        hits_t1 = []
        for kw in cls.TIER_1_KEYWORDS:
            if re.search(kw, text_lower):
                hits_t1.append(kw.replace(r"\b", "").replace(r"[- ]", " "))
        
        if hits_t1:
            # Base risk of 0.20, scales up to 0.49
            risk = min(0.49, 0.20 + 0.05 * len(hits_t1))
            return HeuristicResult(
                risk=round(risk, 2),
                tier_hits=hits_t1,
                trigger_llm=False
            )

        # 4. Safe Base Case (No Hits)
        return HeuristicResult(
            risk=0.05,
            tier_hits=[],
            trigger_llm=False
        )
