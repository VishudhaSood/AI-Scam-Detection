from datetime import datetime
from app.models.schemas import AnalysisResponse, Advisory

class AnalyzerService:
    """
    Service containing the core analysis business logic.
    For Milestone 1, this returns rich, dynamic dummy data mapping real-world
    scam profiles to showcase on the React dashboard.
    """

    @staticmethod
    def analyze_transcript(text: str) -> AnalysisResponse:
        text_lower = text.lower()

        # 1. Define Scam Scenarios for Mocking
        if any(kw in text_lower for kw in ["lottery", "prize", "win", "crore", "lakh"]):
            # Lottery Scam Scenario
            risk_score = 0.92
            label = "SCAM"
            scam_category = "Lottery & Prize Scam"
            deepfake_probability = 0.15  # Normal scammer voice
            explanation = (
                "The conversation exhibits classic patterns of a Lottery Scam. "
                "The caller claims the victim has won a massive prize (KBC or lottery) and demands "
                "an upfront processing fee to release the funds. Authentic lotteries never demand "
                "registration fees via phone."
            )
            advisories = [
                Advisory(
                    title="KBC Lottery & Lucky Draw Frauds",
                    source="RBI (Reserve Bank of India)",
                    description="RBI warns the public against fictitious offers of lottery winnings and cheap funds. RBI never stores money or contacts individuals for lottery payouts.",
                    url="https://www.rbi.org.in/"
                ),
                Advisory(
                    title="Pre-payment scams for Prize Money",
                    source="CERT-In",
                    description="Do not transfer funds to unknown bank accounts claiming to release lottery prizes. It is a scam designed to siphon processing fees.",
                    url="https://www.cert-in.org.in/"
                )
            ]

        elif any(kw in text_lower for kw in ["otp", "bank", "manager", "kyc", "card blocked", "suspend"]):
            # Bank Impersonation / KYC Scam Scenario
            risk_score = 0.98
            label = "SCAM"
            scam_category = "Bank Impersonation (KYC/OTP)"
            deepfake_probability = 0.85  # AI voice cloned as a bank officer
            explanation = (
                "The caller is impersonating a bank official and pressing for immediate action "
                "under the threat of account suspension. They are asking for a One-Time Password (OTP) "
                "or KYC updates. Banks will never ask for OTPs or passwords over a voice call, and "
                "high deepfake probability suggests synthetic voice cloning is being used."
            )
            advisories = [
                Advisory(
                    title="Security Guidelines on Safe Digital Banking",
                    source="RBI",
                    description="Never share OTPs, CVV, passwords, or KYC details with callers. Banks never ask for sensitive credentials via SMS, email, or calls.",
                    url="https://www.rbi.org.in/"
                )
            ]

        elif any(kw in text_lower for kw in ["police", "cbi", "arrest", "customs", "arrest warrant", "illegal"]):
            # Fedex / Customs / Arrest Scam Scenario (very common in India)
            risk_score = 0.95
            label = "SCAM"
            scam_category = "Impersonation of Law Enforcement"
            deepfake_probability = 0.40
            explanation = (
                "The caller is posing as a law enforcement agency (CBI, Customs, or Police) claiming "
                "an illegal package containing contraband was shipped in your name. They are threatening "
                "arrest and demanding immediate payment for clearance. Law enforcement never handles "
                "arrest warrants or legal clearances over video or audio calls with monetary settlements."
            )
            advisories = [
                Advisory(
                    title="Advisory on Cyber Impersonation of Government Agencies",
                    source="CERT-In",
                    description="Citizens are advised not to panic when receiving calls threatening arrest or legal action. Verify credentials directly with local police.",
                    url="https://www.cert-in.org.in/"
                )
            ]

        else:
            # Default/Safe Scenario
            risk_score = 0.12
            label = "SAFE"
            scam_category = "None"
            deepfake_probability = 0.05
            explanation = (
                "The conversation analysis shows normal conversational patterns with no high-risk "
                "scam keywords or urgency cues. Voice quality indicators show typical human biometric markers."
            )
            advisories = []

        return AnalysisResponse(
            transcript=text,
            risk_score=risk_score,
            label=label,
            scam_category=scam_category,
            deepfake_probability=deepfake_probability,
            explanation=explanation,
            advisories=advisories,
            analyzed_at=datetime.utcnow()
        )
