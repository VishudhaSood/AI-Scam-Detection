from fastapi.concurrency import run_in_threadpool
from app.services.evidence_provider import EvidenceProvider, Evidence
from app.services.deepfake_detector import AASISTDetector, DeepfakeResult

class AASISTDeepfakeProvider(EvidenceProvider):
    """
    Evidence provider that runs the AASIST acoustic voice clone / anti-spoofing detector
    on incoming audio frames.
    """
    
    @property
    def name(self) -> str:
        return "deepfake"

    async def evaluate(self, context: dict) -> Evidence:
        session = context.get("session")
        transcript = context.get("transcript", "")
        
        # 1. Try to get pre-calculated result from context
        df_result = context.get("deepfake_result")
        
        # 2. If not provided, but raw audio is in context (e.g. in batch analyze)
        if df_result is None:
            audio_data = context.get("audio_data")
            if audio_data is not None:
                filename = context.get("filename")
                df_result = await run_in_threadpool(
                    AASISTDetector.detect,
                    audio_data,
                    filename,
                    transcript
                )
                
        # 3. Fallback to session cache
        if df_result is None and session is not None:
            df_result = session.last_deepfake_result
            
        # 4. absolute fallback
        if df_result is None:
            df_result = DeepfakeResult(
                probability=None,
                label=None,
                confidence=None,
                model="AASIST",
                latency_ms=0.0
            )

        # Sync back to session if appropriate
        if session is not None:
            session.last_deepfake_result = df_result

        score = df_result.probability if df_result.probability is not None else 0.0
        confidence = df_result.confidence if df_result.confidence is not None else 0.0
        
        explanation = "AASIST voice clone analysis: no speech/audio evaluated yet."
        if df_result.probability is not None:
            explanation = f"AASIST detected voice clone probability of {round(score * 100)}% ({df_result.label})."

        return Evidence(
            source=self.name,
            score=score,
            confidence=confidence,
            weight=0.20,
            details={
                "probability": df_result.probability,
                "label": df_result.label,
                "confidence": df_result.confidence,
                "model": df_result.model,
                "latency_ms": df_result.latency_ms
            },
            explanation=explanation
        )
