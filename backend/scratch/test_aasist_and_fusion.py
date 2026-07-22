import sys
import os
import unittest
import numpy as np

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.deepfake_detector import AASISTDetector, DeepfakeResult
from app.services.risk_engine import EvidenceFusionEngine

class TestAASISTAndFusion(unittest.TestCase):
    def setUp(self):
        # Set environment variables for testing
        os.environ["ENABLE_DEEPFAKE"] = "true"
        os.environ["MODEL_PATH"] = "app/resources/aasist.onnx"
        os.environ["DEEPFAKE_THRESHOLD"] = "0.5"

    def test_aasist_graceful_degradation(self):
        """
        Verify that AASIST detector handles missing model files gracefully
        without throwing exceptions or failing the request.
        """
        # Point to a non-existent path
        os.environ["MODEL_PATH"] = "app/resources/non_existent.onnx"
        
        # Reset the detector state
        AASISTDetector._is_loaded = False
        AASISTDetector._session = None
        
        # Try eager loading
        AASISTDetector.eager_load_model()
        self.assertFalse(AASISTDetector._is_loaded)
        
        # Run detection on empty/dummy bytes
        res = AASISTDetector.detect(b"dummy bytes")
        self.assertIsInstance(res, DeepfakeResult)
        self.assertIsNone(res.probability)
        self.assertIsNone(res.label)
        self.assertIsNone(res.confidence)
        self.assertEqual(res.model, "AASIST")

    def test_evidence_fusion_dynamic_normalization_batch_only(self):
        """
        Dynamic renormalization (excluding the dead verification weight) is only
        safe for a one-shot batch analysis, where there is no persistent
        AdaptiveRiskEngine ratchet floor for a higher ceiling to get stuck against.
        Must be requested explicitly via verification_available=False (what
        api/analyze.py's TempSession sets) — it is NOT the default, because a live
        call's verdict also reads "N/A" before verification has run, and
        renormalizing there crosses the ratchet-latch threshold (see
        test_evidence_fusion_live_call_never_renormalizes below).
        """
        # verification_available=False -> active weights: trans(0.45), heur(0.25), rag(0.20). Sum = 0.90.
        # Inputs: trans=0.50, heur=0.60, advisories=1 (rag_score=0.50), verification="N/A"
        # Weighted sum: 0.50 * 0.45 + 0.60 * 0.25 + 0.50 * 0.20 = 0.225 + 0.15 + 0.10 = 0.475
        # Fused = 0.475 / 0.90 = 0.5277... -> 0.53
        # Floor: max(0.53, 0.50) = 0.53
        fused, breakdown = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=0.50,
            heuristic_risk=0.60,
            advisories_count=1,
            verification_verdict="N/A",
            verification_available=False
        )
        self.assertEqual(fused, 0.53)
        self.assertEqual(breakdown["transcript"], 0.50)
        self.assertEqual(breakdown["heuristics"], 0.60)
        self.assertEqual(breakdown["rag_match"], 0.50)
        self.assertEqual(breakdown["verification"], 0.0)

    def test_evidence_fusion_live_call_never_renormalizes(self):
        """
        A live call (verification_available=True, the default) must NOT
        renormalize even when verdict is "N/A" — that is indistinguishable from
        "hasn't happened yet" on a live call, and renormalizing raises the
        pre-LLM ceiling enough to permanently strand a benign call in VERIFY.
        """
        # Same inputs as the batch test above, but verification_available defaults
        # to True: weights stay fixed at trans(0.45)/heur(0.25)/rag(0.20)/verif(0.10),
        # total=1.0 (verification_score is 0.0 since verdict isn't EVASIVE/etc).
        # Weighted sum: 0.50*0.45 + 0.60*0.25 + 0.50*0.20 + 0 = 0.475. Fused = 0.475 -> 0.47 (floor: max(0.47,0.50)=0.50).
        fused, breakdown = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=0.50,
            heuristic_risk=0.60,
            advisories_count=1,
            verification_verdict="N/A"
        )
        self.assertEqual(fused, 0.50)
        self.assertEqual(breakdown["verification"], 0.0)

    def test_evidence_fusion_with_active_verification(self):
        """
        Verify that evidence fusion includes verification when active (e.g. EVASIVE).
        """
        # Active weights: trans(0.45) + heur(0.25) + rag(0.20) + verif(0.10). Sum = 1.0.
        # Inputs: trans=0.50, heur=0.60, advisories=1 (rag_score=0.50), verification="EVASIVE" (verification_score=1.0)
        # Weighted sum: 0.50*0.45 + 0.60*0.25 + 0.50*0.20 + 1.0*0.10 = 0.225 + 0.15 + 0.10 + 0.10 = 0.575
        # Fused = 0.575 / 1.0 = 0.575 -> 0.58
        # Floor: max(0.58, 0.50) = 0.58
        fused, breakdown = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=0.50,
            heuristic_risk=0.60,
            advisories_count=1,
            verification_verdict="EVASIVE"
        )
        self.assertEqual(fused, 0.57)
        self.assertEqual(breakdown["verification"], 1.0)

    def test_evidence_fusion_transcript_floor(self):
        """
        Test that fused score is always floored at the transcript risk score.
        """
        # Even if heuristics and RAG are low, fused score must be >= transcript risk.
        # Inputs: trans=0.80, heur=0.10, advisories=0 (rag_score=0.0), verification="PLAUSIBLE" (verification_score=0.0, weight=0.10)
        # Weights: sum=1.0. Weighted sum: 0.80 * 0.45 + 0.10 * 0.25 + 0.0 + 0.0 = 0.36 + 0.025 = 0.385.
        # Fused = 0.385 / 1.0 = 0.39.
        # Floor: max(0.39, 0.80) = 0.80.
        fused, _ = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=0.80,
            heuristic_risk=0.10,
            advisories_count=0,
            verification_verdict="PLAUSIBLE"
        )
        self.assertEqual(fused, 0.80)

    def test_confidence_engine_logic(self):
        """
        Verify the ConfidenceEngine upgrades:
        - Non-linear square-root word factor: sqrt(word_count/40) capped at 1.0.
        - Baseline audit factor: 1.0 if llm_audits_done >= 1, else 0.40.
        - Non-penalizing RAG: 1.0 if retrieval_hits > 0, else 0.85.
        - Threat level boost: >=0.85 if risk_score >= 0.75, >=0.70 if risk_score >= 0.40.
        """
        from app.services.risk_engine import ConfidenceEngine

        # Test Case 1: Short text threat (20 words), 1 audit, 0 audio, 0 hits
        # word_factor = sqrt(20/40) = 0.707
        # audit_factor = 1.0
        # audio_factor = 1.0
        # retrieval_factor = 0.85
        # geom_mean = (0.707 * 1.0 * 1.0 * 0.85) ** 0.25 = (0.601) ** 0.25 = 0.88
        # With risk_score = 0.95 (SCAM): boost sets it to max(0.88, 0.85) = 0.88
        conf = ConfidenceEngine.calculate_confidence(
            word_count=20,
            llm_audits_done=1,
            audio_seconds=0.0,
            retrieval_hits=0,
            risk_score=0.95
        )
        self.assertEqual(conf, 0.88)

        # Test Case 2: Very short call, 0 audits, 5s audio (early phase)
        # word_factor = sqrt(5/40) = 0.353
        # audit_factor = 0.40
        # audio_factor = 5.0/30.0 = 0.167
        # retrieval_factor = 0.85
        # geom_mean = (0.353 * 0.40 * 0.167 * 0.85) ** 0.25 = 0.38
        # With risk_score = 0.10: no boost
        conf = ConfidenceEngine.calculate_confidence(
            word_count=5,
            llm_audits_done=0,
            audio_seconds=5.0,
            retrieval_hits=0,
            risk_score=0.10
        )
        self.assertEqual(conf, 0.38)

        # Test Case 3: High threat boost verification
        # Suppose confidence math yields a low score due to short word count,
        # but risk is high (0.80). The confidence should be boosted to at least 0.85.
        conf = ConfidenceEngine.calculate_confidence(
            word_count=1,
            llm_audits_done=0,
            audio_seconds=0.0,
            retrieval_hits=0,
            risk_score=0.80
        )
        self.assertGreaterEqual(conf, 0.85)

if __name__ == "__main__":
    unittest.main()
