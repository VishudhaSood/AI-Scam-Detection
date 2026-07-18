class RiskEngine:
    """
    Engine that combines voice deepfake analysis and content-based scam risk
    to produce a unified risk score and security classification label.
    """

    @staticmethod
    def calculate_combined_risk(deepfake_prob: float, llm_risk_score: float, is_text_only: bool = False) -> tuple[float, str]:
        """
        Combines deepfake probability and LLM transcription threat scores.
        
        Weights:
        - Voice Deepfake probability: 30% (0.3)
        - Content LLM risk score: 70% (0.7)
        
        Overrides:
        - If voice cloning is highly probable (> 0.8) and content risk is moderate (> 0.5),
          force the classification to SCAM (risk score >= 0.9).
        - If content risk is extremely high (> 0.95), force label to SCAM.
        - If is_text_only is True (e.g. no audio is analyzed), bypass the voice clone 30% weight
          and set threat directly to the content LLM score.
        
        Returns:
            tuple[float, str]: (combined_risk_score, label)
                Where combined_risk_score is between 0.0 and 1.0, 
                and label is one of: "SAFE", "SUSPICIOUS", "SCAM"
        """
        # Ensure bounds
        deepfake_prob = max(0.0, min(1.0, deepfake_prob))
        llm_risk_score = max(0.0, min(1.0, llm_risk_score))

        # 1. Base Weighted Score or Text-Only Bypass
        if is_text_only:
            combined = llm_risk_score
        else:
            combined = (deepfake_prob * 0.3) + (llm_risk_score * 0.7)

        # 2. Apply Rule-Based Overrides
        # Rule A: High-risk deepfake combined with scam content triggers automatic SCAM escalation
        if not is_text_only and deepfake_prob > 0.8 and llm_risk_score > 0.5:
            combined = max(combined, 0.95)
            
        # Rule B: Extreme content threat triggers automatic SCAM escalation
        if llm_risk_score > 0.95:
            combined = max(combined, 0.98)

        # Round to 2 decimal places
        combined = round(combined, 2)

        # 3. Classify Security Label
        if combined >= 0.8:
            label = "SCAM"
        elif combined >= 0.4:
            label = "SUSPICIOUS"
        else:
            label = "SAFE"

        return combined, label


import time

class AdaptiveRiskEngine:
    """
    Stateful risk engine for live calls (Milestone 8).
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

    def process_cycle(self, risk_raw: float, word_count: int, llm_audits_done: int) -> tuple[float, float, str]:
        """
        Runs one cycle of the stateful risk engine:
        1. Smooth raw risk using EMA (alpha = 0.35)
        2. Apply ratchet floor
        3. Compute confidence
        4. Compute next mode with hysteresis
        
        Returns:
            tuple[float, float, str]: (smoothed_risk, confidence, mode)
        """
        # 1. EMA Smoothing
        alpha = 0.35
        # If it's the very first cycle, initialize smoothed_risk directly to risk_raw
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
        # confidence = min(1.0, words_heard / 120) * min(1.0, llm_audits_done / 2)
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
            # MONITOR -> VERIFY: Instant transition when risk >= 0.40
            if natural_mode in ["VERIFY", "DANGER"]:
                self.mode = "VERIFY"
                self.verify_exit_low_start = None
            
        elif self.mode == "VERIFY":
            # VERIFY -> DANGER: Instant transition when risk >= 0.75
            if natural_mode == "DANGER":
                self.mode = "DANGER"
                self.danger_exit_low_start = None
            # VERIFY -> MONITOR: Exits below 0.35 sustained for 15s
            elif self.smoothed_risk < 0.35:
                if self.verify_exit_low_start is None:
                    self.verify_exit_low_start = now
                elif now - self.verify_exit_low_start >= 15.0:
                    self.mode = "MONITOR"
                    self.verify_exit_low_start = None
            else:
                self.verify_exit_low_start = None

        elif self.mode == "DANGER":
            # DANGER -> VERIFY: Exits below 0.65 sustained for 20s
            if self.smoothed_risk < 0.65:
                if self.danger_exit_low_start is None:
                    self.danger_exit_low_start = now
                elif now - self.danger_exit_low_start >= 20.0:
                    self.mode = "VERIFY"
                    self.danger_exit_low_start = None
            else:
                self.danger_exit_low_start = None

        return self.smoothed_risk, confidence, self.mode
