from app.services.evidence_provider import EvidenceProvider, Evidence

class VerificationProvider(EvidenceProvider):
    """
    Evidence provider checking the scammer's reaction to identity-verification questions.
    Triggers penalty if the caller refuses, is evasive, or threatens.
    """
    
    @property
    def name(self) -> str:
        return "verification"

    async def evaluate(self, context: dict) -> Evidence:
        session = context.get("session")
        
        verdict = context.get("verification_verdict")
        if verdict is None and session is not None:
            verdict = getattr(session, "llm_verdict", "N/A")
            
        if verdict is None:
            verdict = "N/A"

        score = 0.0
        confidence = 0.0
        explanation = "No verification questions asked yet."
        
        if verdict in ["EVASIVE", "REFUSED", "THREATENED"]:
            score = 1.0
            confidence = 1.0
            explanation = f"Verification failure: caller responded with status {verdict}."
        elif verdict == "PLAUSIBLE":
            score = 0.0
            confidence = 1.0
            explanation = "Verification success: caller gave a plausible explanation."
        elif verdict == "NOT_YET_ANSWERED":
            score = 0.0
            confidence = 0.5
            explanation = "Verification questions asked; waiting for caller response."

        return Evidence(
            source=self.name,
            score=score,
            confidence=confidence,
            weight=0.10,
            details={
                "verdict": verdict
            },
            explanation=explanation
        )
