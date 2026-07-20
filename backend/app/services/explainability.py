from typing import List
from app.services.evidence_provider import Evidence

class ExplainabilityEngine:
    """
    Service responsible for converting the structured multi-provider evidence list,
    fused scores, and adaptive risk states into a human-readable trace.
    """
    
    @staticmethod
    def generate_trace(
        evidence_list: List[Evidence],
        raw_risk: float,
        smoothed_risk: float,
        mode: str
    ) -> List[str]:
        trace = []
        
        # 1. Add individual provider evaluation reports
        for ev in evidence_list:
            # Only include providers that contributed or had active evaluations
            if ev.score > 0.0 or ev.confidence > 0.0:
                # Clean source name
                source_label = ev.source.replace("_", " ").title()
                score_pct = f"{round(ev.score * 100)}%" if ev.score is not None else "N/A"
                conf_pct = f"{round(ev.confidence * 100)}%"
                trace.append(
                    f"[{source_label}] Risk contribution: {score_pct} (Confidence: {conf_pct}) - {ev.explanation}"
                )
                
        # 2. Add fusion step trace
        trace.append(
            f"[Evidence Fusion] Combined multi-factor threat level evaluated at {round(raw_risk * 100)}%. "
            f"Weights: Transcript AI (45%), Keyword Heuristics (25%), RAG Advisories (20%), Verification Question Verdict (10%)."
        )
        
        # 3. Add state machine and temporal risk trace
        trace.append(
            f"[Temporal Adaptation] Smoothed display risk: {round(smoothed_risk * 100)}%. Active coaching mode: {mode}."
        )
        
        return trace
