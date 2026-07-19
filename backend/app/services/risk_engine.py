import time
import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger("app.services.risk_engine")

class EvidenceFusionEngine:
    """
    Combines multiple independent signals into a single unified scam risk score
    using a configurable, weighted evidence fusion layer.
    
    Guarantees:
    - No single source alone determines the final classification.
    - Deepfake probability increases suspicion but never triggers DANGER (scam state) alone.
    - Low deepfake score never pulls down transcript-based risk.
    """
    
    # Configurable weights for each evidence component
    # Sum of all weights = 1.0
    WEIGHTS = {
        "transcript": 0.40,      # Qwen LLM analysis
        "deepfake": 0.20,        # AASIST voice anti-spoofing
        "heuristics": 0.20,      # Tiered keyword scanner
        "rag_match": 0.10,       # ChromaDB advisory match count
        "verification": 0.10      # Caller response to verification questions
    }

    @classmethod
    def fuse_evidence(
        cls,
        transcript_risk: float,
        deepfake_prob: Optional[float],
        heuristic_risk: float,
        advisories_count: int,
        verification_verdict: str
    ) -> Tuple[float, Dict[str, float]]:
        """
        Merges 5 evidence dimensions into a raw fused score.
        
        Args:
            transcript_risk: Score from LLM (0.0 to 1.0)
            deepfake_prob: Probability of synthetic voice (0.0 to 1.0, or None if failed)
            heuristic_risk: Score from keyword tiers (0.0 to 1.0)
            advisories_count: Number of semantically matched advisories
            verification_verdict: EVASIVE, REFUSED, THREATENED, PLAUSIBLE, etc.
            
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

        # 3. Handle missing components (e.g. if AASIST failed and returned None)
        active_weights = dict(cls.WEIGHTS)
        if deepfake_prob is None:
            active_weights["deepfake"] = 0.0

        total_weight = sum(active_weights.values())
        if total_weight == 0:
            total_weight = 1.0

        # 4. Compute weighted sum
        weighted_sum = (
            transcript_risk * active_weights["transcript"] +
            (deepfake_prob or 0.0) * active_weights["deepfake"] +
            heuristic_risk * active_weights["heuristics"] +
            rag_score * active_weights["rag_match"] +
            verification_score * active_weights["verification"]
        )
        fused = weighted_sum / total_weight

        # 5. Constraint A: A low deepfake score must NEVER pull down or reduce transcript-based risk
        if deepfake_prob is not None:
            fused = max(fused, transcript_risk)

        # 6. Constraint B: Deepfake probability alone cannot classify a call as a scam.
        # If the overall score crosses the DANGER threshold (>= 0.75), but both
        # transcript content risk and keyword heuristics are low (< 0.40),
        # cap the risk at 0.74 (keeping it in VERIFY mode).
        if fused >= 0.75:
            if transcript_risk < 0.40 and heuristic_risk < 0.40:
                fused = 0.74

        # Round to 2 decimal places
        fused_score = round(max(0.0, min(1.0, fused)), 2)

        # Build intermediate breakdown dictionary
        breakdown = {
            "transcript": round(transcript_risk, 2),
            "deepfake": round(deepfake_prob, 2) if deepfake_prob is not None else 0.0,
            "heuristics": round(heuristic_risk, 2),
            "rag_match": round(rag_score, 2),
            "verification": round(verification_score, 2)
        }

        return fused_score, breakdown


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

    def process_cycle(self, risk_raw: float, word_count: int, llm_audits_done: int) -> Tuple[float, float, str]:
        """
        Runs one cycle of the stateful risk engine:
        1. Smooth raw risk using EMA (alpha = 0.35)
        2. Apply ratchet floor
        3. Compute confidence
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

        # 3. Confidence Calculation
        word_factor = min(1.0, word_count / 120.0)
        audit_factor = min(1.0, llm_audits_done / 2.0)
        confidence = round(word_factor * audit_factor, 2)

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
