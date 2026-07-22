import re
from dataclasses import dataclass
from typing import List


# --- Negation handling: protective-advice whitelist -------------------------
# The scanner must fire on "share your OTP" (a scammer speaking) yet stay silent
# on "never share your OTP" (safety advice). The previous approach asked "is a
# negation word within 60 characters BEFORE the keyword?" — a backward window
# that breaks two ways: a second keyword outside the window still fires ("never
# ask for your OTP or PIN" — PIN escapes and fires), and Hinglish postfix
# negation ("OTP mat batao") puts the negation AFTER the keyword, where no
# backward window can ever see it.
#
# Instead we match a closed list of protective-advice phrasings against the
# CLAUSE containing the keyword (reading forward as well as back). This inverts
# the failure mode: missing a protective phrasing costs one LLM audit that
# corrects it (cheap), never a blinded scanner on a real scam (expensive).
PROTECTIVE_PATTERNS = [
    re.compile(p) for p in (
        # "<authority> will never ask/call/send ..." — institutional reassurance
        r"\b(bank|rbi|we|they|nobody|no one|officials?|police)\b[^.,;]{0,25}"
        r"\b(never|won'?t|will not|do not|don'?t)\b[^.,;]{0,15}"
        r"\b(ask|request|call|send|demand)",
        # "never/don't share|give|tell ..." — direct protective instruction
        r"\b(never|do not|don'?t|dont)\s+(share|give|send|tell|disclose|reveal|provide)\b",
        # "no payment/fee is required/involved ..."
        r"\bno\s+(payment|fee|charge|money|amount)\b[^.,;]{0,20}\b(required|needed|involved|asked)\b",
        r"\b(is|are)\s+not\s+required\b",
        # Hinglish postfix negation: "OTP mat batao", "paise mat bhejo"
        r"\bmat\s+(do|dena|batao|bhejo|bhejna)\b",
        # "warning about <scam>"
        r"\bwarning\s+about\b",
    )
]

# The inspected clause runs from the previous punctuation up to this many
# characters PAST the keyword, so postfix negation stays inside it.
_CLAUSE_LOOKAHEAD = 40


@dataclass
class HeuristicResult:
    """
    Data contract output for the Heuristic Scorer module.
    """
    risk: float
    tier_hits: List[str]
    trigger_llm: bool


def _is_negated(text_lower: str, match_start: int) -> bool:
    """
    Returns True when the keyword at `match_start` sits inside a clause that is
    protective advice ("bank will never ask for your OTP", "OTP mat batao")
    rather than a live scam instruction — in which case the hit is suppressed,
    because the speaker is warning against the action, not performing it.

    The clause runs from the previous sentence/clause punctuation up to a short
    look-ahead past the keyword, so both a negation BEFORE the keyword ("never
    share your OTP") and one AFTER it ("OTP mat batao") fall inside the span we
    inspect. Kept under this name because app.rag.query_engine imports it.
    """
    clause_start = max(
        0,
        text_lower.rfind(",", 0, match_start) + 1,
        text_lower.rfind(".", 0, match_start) + 1,
        text_lower.rfind(";", 0, match_start) + 1,
    )
    clause = text_lower[clause_start:match_start + _CLAUSE_LOOKAHEAD]
    return any(p.search(clause) for p in PROTECTIVE_PATTERNS)


class HeuristicScorer:
    """
    Scorer service running tiered keyword analyses on conversation text.
    Executes instantly on the CPU, providing raw risk hints for the streaming cycle.
    Includes negation awareness and multilingual Hinglish scam keyword scanning.
    """

    # Tier 3 (Risk: 0.85 - 0.98): Extreme threat indicators triggering immediate LLM audit
    TIER_3_KEYWORDS = [
        r"\botp\b", r"\bone[- ]time[- ]password\b", r"\bcvv\b", r"\bpin\b", r"\bpassword\b",
        r"\banydesk\b", r"\bteamviewer\b", r"\brustdesk\b", r"\bscreen[- ]share\b", r"\bremote[- ]access\b",
        r"\btransfer[- ]money\b", r"\bsend[- ]money\b", r"\bdeposit[- ]fee\b", r"\bprocessing[- ]fee\b",
        r"\bpayment\b", r"\barreste?d?\b", r"\bwarrant\b", r"\bcbi\b", r"\bpolice[- ]custody\b",
        r"\bcontraband\b", r"\billegal[- ]package\b",
        # Digital Arrest & Law Enforcement specific
        r"\bdigital[- ]arrest\b", r"\bcyber[- ]police\b", r"\bcyber[- ]cell\b",
        r"\bnarcotics\b", r"\bsettlement[- ]fee\b",
        # Hinglish scam indicators
        r"\bpaisa[- ]transfer\b", r"\bpaise[- ]bhejo\b", r"\bgiraftari\b",
        r"\bpolice[- ]aayegi\b", r"\barrest[- ]kar\b", r"\bpenalty[- ]bharna\b",
        r"\bkhata[- ]block\b",
    ]

    # Tier 2 (Risk: 0.50 - 0.74): Medium threat signals of identity fraud and baiting
    TIER_2_KEYWORDS = [
        r"\bkyc\b", r"\bknow[- ]your[- ]customer\b", r"\bupdate[- ]account\b", r"\bsuspend\b",
        r"\bblock(?:ed)?\b", r"\bcard[- ]blocked\b", r"\bverification\b", r"\blottery\b", r"\bprize\b",
        r"\blucky[- ]draw\b", r"\bcrore\b", r"\blakh\b", r"\bwin\b", r"\bcustoms\b",
        r"\bfedex\b", r"\bdhl\b", r"\bcourier\b", r"\billegal\b",
        # Digital Arrest & Regional variants
        r"\bfake[- ]warrant\b", r"\bvideo[- ]call[- ]arrest\b",
        r"\bkhata\b", r"\binam\b", r"\blottery[- ]lagi\b", r"\bpaise[- ]jeete\b",
        r"\bbijli[- ]bill\b", r"\bpower[- ]cut\b",
    ]

    # Tier 1 (Risk: 0.20 - 0.49): Urgency-building keywords and pressure language
    TIER_1_KEYWORDS = [
        r"\burgent\b", r"\bdo[n']t[- ]tell[- ]anyone\b", r"\bkeep[- ]it[- ]secret\b",
        r"\bconfidential\b", r"\bemergency\b", r"\bcritical\b", r"\bimmediately\b",
        r"\bnow\b", r"\bwithin[- ]1[- ]hour\b",
        # Hinglish urgency words
        r"\babhi\b", r"\bjaldi\b", r"\bkisi[- ]ko[- ]mat[- ]batao\b", r"\bgupt\b",
    ]

    @classmethod
    def _match_keywords(cls, text_lower: str, keywords: list) -> List[str]:
        """
        Matches keywords against text with negation suppression.
        Returns the list of non-negated keyword hits.
        """
        hits = []
        for kw in keywords:
            match = re.search(kw, text_lower)
            if match:
                # Check if the keyword is negated in context
                if _is_negated(text_lower, match.start()):
                    continue  # Skip — speaker is warning, not threatening
                hits.append(kw.replace(r"\b", "").replace(r"[- ]", " "))
        return hits

    @classmethod
    def score(cls, text: str) -> HeuristicResult:
        """
        Scores the input text block using three-tiered keyword match rules.
        Negated keywords (preceded by "don't", "never", etc.) are suppressed.
        """
        text_lower = text.lower()
        
        # 1. Match Tier 3 (High Threat)
        hits_t3 = cls._match_keywords(text_lower, cls.TIER_3_KEYWORDS)
        
        if hits_t3:
            # Base risk of 0.85, scales up to 0.98 based on quantity of hits
            risk = min(0.98, 0.85 + 0.02 * len(hits_t3))
            return HeuristicResult(
                risk=round(risk, 2),
                tier_hits=hits_t3,
                trigger_llm=True
            )

        # 2. Match Tier 2 (Medium Threat)
        hits_t2 = cls._match_keywords(text_lower, cls.TIER_2_KEYWORDS)
        
        if hits_t2:
            # Base risk of 0.50, scales up to 0.74
            risk = min(0.74, 0.50 + 0.04 * len(hits_t2))
            return HeuristicResult(
                risk=round(risk, 2),
                tier_hits=hits_t2,
                trigger_llm=False
            )

        # 3. Match Tier 1 (Low Threat/Urgency)
        hits_t1 = cls._match_keywords(text_lower, cls.TIER_1_KEYWORDS)
        
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
