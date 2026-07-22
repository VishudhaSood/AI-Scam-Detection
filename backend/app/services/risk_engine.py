import time
import logging
from typing import Optional, Dict, Tuple, List, Any

logger = logging.getLogger("app.services.risk_engine")

class EvidenceFusionEngine:
    """
    Combines multiple independent signals into a single unified scam risk score
    using a configurable, weighted evidence fusion layer.
    
    Guarantees:
    - No single source alone determines the final classification.
    - Transcript floor: the fused score is always at least as high as the transcript risk.
    """
    
    # Configurable weights for each evidence component. Sum = 1.0.
    # Note: Deepfake/AASIST removed — its parallel mic capture degraded WebSpeech.
    #
    # Transcript (the LLM) is the semantic authority, but its dimension is 0 until
    # the first audit fires — so before the LLM the score can climb no higher than
    # (1 - transcript). At transcript 0.60 that pre-LLM cap is 0.40, which left a
    # loud-keyword scam sitting in MONITOR (SAFE) through the opening seconds and
    # whenever Groq was rate-limited. Reverting transcript to 0.45 lifts the cap to
    # 0.55 and gives the always-available keyword tripwire enough weight (0.25) to
    # reach VERIFY on its own. This costs no LLM authority: the transcript FLOOR in
    # fuse_evidence already pins the score to the LLM the instant it audits,
    # regardless of weight. Depends on the protective-phrase negation fix in
    # heuristic_scorer.py — 0.25 also re-arms keyword false positives, which that
    # fix keeps quiet (and the 0.55 cap keeps any that slip through reversible).
    WEIGHTS = {
        "transcript": 0.45,      # LLM analysis (Groq llama-3.3) - primary semantic authority
        "heuristics": 0.25,      # Fast keyword scanner - tripwire that can reach VERIFY pre-LLM
        "rag_match": 0.20,       # ChromaDB advisory match strength
        "verification": 0.10      # Caller response to verification questions
    }

    @classmethod
    def fuse_evidence_list(
        cls,
        evidence_list: List[Any],
        verification_available: bool = True
    ) -> Tuple[float, Dict[str, float]]:
        """
        Adapts the new EvidenceProvider outputs to the fusion logic.

        verification_available: False only for a one-shot batch analysis (see
        api/analyze.py's TempSession), where the verification dimension can never
        fire. Defaults True — the live-call-safe behaviour — so any caller that
        doesn't pass it keeps today's fixed weights.
        """
        # Map list of Evidence into dict
        ev_dict = {ev.source: ev for ev in evidence_list}

        transcript_risk = ev_dict["transcript"].score if "transcript" in ev_dict else 0.0
        heuristic_risk = ev_dict["heuristics"].score if "heuristics" in ev_dict else 0.0
        rag_score = ev_dict["rag_match"].score if "rag_match" in ev_dict else 0.0
        verification_score = ev_dict["verification"].score if "verification" in ev_dict else 0.0

        advisories_count = int(rag_score * 2.0)

        # Determine verdict string
        verification_verdict = "N/A"
        if "verification" in ev_dict:
            verification_verdict = ev_dict["verification"].details.get("verdict", "N/A")

        return cls.fuse_evidence(
            transcript_risk=transcript_risk,
            heuristic_risk=heuristic_risk,
            advisories_count=advisories_count,
            verification_verdict=verification_verdict,
            verification_available=verification_available
        )

    @classmethod
    def fuse_evidence(
        cls,
        transcript_risk: float,
        heuristic_risk: float,
        advisories_count: int,
        verification_verdict: str,
        verification_available: bool = True
    ) -> Tuple[float, Dict[str, float]]:
        """
        Merges 4 evidence dimensions into a raw fused score.

        Args:
            transcript_risk: Score from LLM (0.0 to 1.0)
            heuristic_risk: Score from keyword tiers (0.0 to 1.0)
            advisories_count: Number of semantically matched advisories
            verification_verdict: EVASIVE, REFUSED, THREATENED, PLAUSIBLE, etc.
            verification_available: whether this call could EVER produce a
                verification verdict. False for one-shot batch analyses (there is
                no caller-verification loop there), True for a live call.

        Returns:
            Tuple[float, Dict[str, float]]: (fused_score, evidence_breakdown)
        """
        # 1. Map RAG matching to a score [0.0 - 1.0]
        # 1 advisory = 0.5 strength, 2+ advisories = 1.0 strength
        rag_score = min(1.0, advisories_count * 0.5)

        # 2. Map verification response to a score [0.0 - 1.0]
        if verification_verdict in ["EVASIVE", "REFUSED", "THREATENED"]:
            verification_score = 1.0
        else:
            verification_score = 0.0

        # 3. Determine active weights dynamically.
        # Renormalizing away the (structurally dead) verification weight is safe
        # ONLY when verification could never fire at all (a one-shot batch
        # analysis) — there the score is computed once and discarded, so there is
        # no persistent ratchet floor for a higher ceiling to get stuck against.
        # A LIVE call's AdaptiveRiskEngine persists across many cycles; verdict
        # also reads "N/A" there before verification has had a chance to run, so
        # verdict alone can't tell the two apart. Renormalizing on a live call
        # raises the pre-LLM ceiling just enough (0.45 -> 0.50) to cross the
        # ratchet-latch threshold (floor = 0.75 x peak never falls below the
        # VERIFY-exit cutoff), permanently stranding a benign call in VERIFY even
        # after the LLM later confirms SAFE. So: only renormalize when this
        # analysis structurally can never receive a verification verdict.
        weights = cls.WEIGHTS.copy()
        if not verification_available and verification_verdict in ["N/A", "NOT_YET_ANSWERED"]:
            weights["verification"] = 0.0

        total_weight = sum(weights.values())
        if total_weight <= 0.0:
            total_weight = 1.0

        # 4. Compute weighted sum
        weighted_sum = (
            transcript_risk * weights["transcript"] +
            heuristic_risk * weights["heuristics"] +
            rag_score * weights["rag_match"] +
            verification_score * weights["verification"]
        )
        fused = weighted_sum / total_weight

        # 5. Transcript floor: the fused score is always at least as high as the
        #    transcript risk. This prevents weak heuristic/RAG scores from diluting
        #    a strong LLM signal (fixes FLAWS §2.4).
        fused = max(fused, transcript_risk)

        # Round to 2 decimal places
        fused_score = round(max(0.0, min(1.0, fused)), 2)

        # Build intermediate breakdown dictionary
        breakdown = {
            "transcript": round(transcript_risk, 2),
            "heuristics": round(heuristic_risk, 2),
            "rag_match": round(rag_score, 2),
            "verification": round(verification_score, 2)
        }

        return fused_score, breakdown


class ConfidenceEngine:
    """
    Multi-factor engine that dynamically estimates overall confidence
    of the scam classification using transcript length, LLM audit depth,
    audio duration analyzed, and RAG warnings matched.
    """
    
    @classmethod
    def calculate_confidence(
        cls,
        word_count: int,
        llm_audits_done: int,
        audio_seconds: float = 0.0,
        retrieval_hits: int = 0,
        risk_score: float = 0.0
    ) -> float:
        # 1. Transcript length coverage (softer non-linear scaling)
        # Baseline factor starts high with small counts, reaching 1.0 at 40+ words.
        word_factor = min(1.0, (word_count / 40.0) ** 0.5) if word_count > 0 else 0.0
        
        # 2. AI Reasoning depth
        # If at least 1 LLM audit has run, we have full AI reasoning confidence (1.0).
        # Otherwise, if only heuristics are active, confidence is lower (0.40).
        audit_factor = 1.0 if llm_audits_done >= 1 else 0.40
        
        # 3. Audio exposure (benchmark: 30 seconds, softer scaling)
        audio_factor = min(1.0, audio_seconds / 30.0) if audio_seconds > 0.0 else 1.0
        
        # 4. Regulatory database alignment
        # Having matched warnings adds confidence, but lack of matches does not penalize (default 0.85).
        retrieval_factor = 1.0 if retrieval_hits > 0 else 0.85

        # Blended geometric mean to prevent single-factor overconfidence
        factors = [word_factor, audit_factor, audio_factor, retrieval_factor]
        clamped_factors = [max(0.10, f) for f in factors]
        
        import math
        geom_mean = math.prod(clamped_factors) ** (1.0 / len(clamped_factors))
        confidence = round(geom_mean, 2)
        
        # Boost confidence when threat level is high
        # If we are certain there is a scam (risk_score >= 0.75), confidence must be at least 0.85.
        # If it is suspicious (risk_score >= 0.40), confidence must be at least 0.70.
        if risk_score >= 0.75:
            confidence = max(confidence, 0.85)
        elif risk_score >= 0.40:
            confidence = max(confidence, 0.70)
            
        return round(max(0.10, min(1.0, confidence)), 2)


class AdaptiveRiskEngine:
    """
    Stateful risk engine for live calls.
    Tracks EMA smoothing, ratchet floor, confidence, and state machine with hysteresis.
    """
    def __init__(self):
        # Per-session state
        self.smoothed_risk = 0.0
        self.peak_smoothed = 0.0
        self.ratchet_floor = 0.0
        self.mode = "MONITOR"  # MONITOR | VERIFY | DANGER
        
        # Timestamps for exit timers (hysteresis)
        self.verify_exit_low_start = None  # Start timestamp when risk < 0.35 sustained
        self.danger_exit_low_start = None  # Start timestamp when risk < 0.65 sustained
 
    def process_cycle(
        self,
        risk_raw: float,
        word_count: int,
        llm_audits_done: int,
        audio_seconds: float = 0.0,
        retrieval_hits: int = 0
    ) -> Tuple[float, float, str]:
        """
        Runs one cycle of the stateful risk engine:
        1. Smooth raw risk using EMA (alpha = 0.35)
        2. Apply ratchet floor
        3. Compute confidence via ConfidenceEngine
        4. Compute next mode with hysteresis
        
        Returns:
            Tuple[float, float, str]: (smoothed_risk, confidence, mode)
        """
        # 1. EMA Smoothing
        alpha = 0.35
        if self.smoothed_risk == 0.0 and self.peak_smoothed == 0.0:
            self.smoothed_risk = risk_raw
        else:
            self.smoothed_risk = alpha * risk_raw + (1 - alpha) * self.smoothed_risk
            
        # 2. Ratchet Floor
        self.peak_smoothed = max(self.peak_smoothed, self.smoothed_risk)
        self.ratchet_floor = max(self.ratchet_floor, 0.75 * self.peak_smoothed)
        self.smoothed_risk = max(self.smoothed_risk, self.ratchet_floor)
        
        # Round smoothed risk
        self.smoothed_risk = round(max(0.0, min(1.0, self.smoothed_risk)), 2)
 
        # 3. Dynamic Confidence Calculation
        confidence = ConfidenceEngine.calculate_confidence(
            word_count=word_count,
            llm_audits_done=llm_audits_done,
            audio_seconds=audio_seconds,
            retrieval_hits=retrieval_hits,
            risk_score=self.smoothed_risk
        )

        # 4. State Machine & Hysteresis
        now = time.time()
        
        # Evaluate natural target state based on raw thresholds
        if self.smoothed_risk >= 0.75:
            natural_mode = "DANGER"
        elif self.smoothed_risk >= 0.40:
            natural_mode = "VERIFY"
        else:
            natural_mode = "MONITOR"

        # Apply state transitions with hysteresis
        if self.mode == "MONITOR":
            if natural_mode in ["VERIFY", "DANGER"]:
                self.mode = "VERIFY"
                self.verify_exit_low_start = None
            
        elif self.mode == "VERIFY":
            if natural_mode == "DANGER":
                self.mode = "DANGER"
                self.danger_exit_low_start = None
            elif self.smoothed_risk < 0.35:
                if self.verify_exit_low_start is None:
                    self.verify_exit_low_start = now
                elif now - self.verify_exit_low_start >= 15.0:
                    self.mode = "MONITOR"
                    self.verify_exit_low_start = None
            else:
                self.verify_exit_low_start = None

        elif self.mode == "DANGER":
            if self.smoothed_risk < 0.65:
                if self.danger_exit_low_start is None:
                    self.danger_exit_low_start = now
                elif now - self.danger_exit_low_start >= 20.0:
                    self.mode = "VERIFY"
                    self.danger_exit_low_start = None
            else:
                self.danger_exit_low_start = None

        return self.smoothed_risk, confidence, self.mode
