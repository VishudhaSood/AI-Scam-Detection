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
