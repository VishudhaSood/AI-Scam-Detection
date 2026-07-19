import asyncio
from typing import Dict, Any, List
from app.services.evidence_provider import Evidence, EvidenceProvider
from app.services.providers import (
    WhisperReasoningProvider,
    AASISTDeepfakeProvider,
    HeuristicScorerProvider,
    RAGAdvisoryProvider,
    VerificationProvider
)
from app.services.risk_engine import EvidenceFusionEngine

class EvidenceOrchestrator:
    """
    Central orchestration engine that aggregates signals from Whisper, AASIST,
    heuristics, RAG databases, and caller verification responses, then routes them
    through the evidence fusion and state machine layers.
    """
    
    def __init__(self):
        self.providers: List[EvidenceProvider] = [
            WhisperReasoningProvider(),
            AASISTDeepfakeProvider(),
            HeuristicScorerProvider(),
            RAGAdvisoryProvider(),
            VerificationProvider()
        ]

    async def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Coordinates concurrent evaluation of all evidence providers, combines
        their metrics, runs stateful risk filters, and generates a trace.
        """
        # Run all registered providers concurrently
        tasks = [provider.evaluate(context) for provider in self.providers]
        evidence_list: List[Evidence] = await asyncio.gather(*tasks)
        
        # 1. Run multi-source Evidence Fusion Engine
        fused_score, breakdown = EvidenceFusionEngine.fuse_evidence_list(evidence_list)
        
        # 2. Run stateful temporal risk filters and state machine
        session = context.get("session")
        transcript = context.get("transcript", "")
        word_count = len(transcript.split())
        
        if session is not None:
            # Live monitoring path: run the AdaptiveRiskEngine to smooth, ratchet and transition
            smoothed_risk, confidence, mode = session.risk_engine.process_cycle(
                risk_raw=fused_score,
                word_count=word_count,
                llm_audits_done=session.llm_audits_done
            )
            # Sync session breakdown cache
            session.last_breakdown = breakdown
        else:
            # Batch/static path: evaluate static properties without ratchet floor / state transitions
            smoothed_risk = fused_score
            mode = "MONITOR"
            if smoothed_risk >= 0.75:
                mode = "DANGER"
            elif smoothed_risk >= 0.40:
                mode = "VERIFY"
                
            # Estimate confidence via ConfidenceEngine in batch mode
            from app.services.risk_engine import ConfidenceEngine
            advisories_count = breakdown.get("rag_match", 0.0) * 2.0
            # For batch file analyze, we estimate audio duration as 30 seconds if we have a file
            audio_seconds = 30.0 if context.get("audio_data") is not None else 0.0
            confidence = ConfidenceEngine.calculate_confidence(
                word_count=word_count,
                llm_audits_done=1 if transcript.strip() else 0,
                audio_seconds=audio_seconds,
                retrieval_hits=int(advisories_count)
            )

        # 3. Generate human-readable explainability reasoning trace
        from app.services.explainability import ExplainabilityEngine
        reasoning_trace = ExplainabilityEngine.generate_trace(
            evidence_list, fused_score, smoothed_risk, mode
        )

        return {
            "risk_raw": fused_score,
            "risk_smoothed": smoothed_risk,
            "confidence": confidence,
            "mode": mode,
            "evidence_breakdown": breakdown,
            "reasoning_trace": reasoning_trace
        }
