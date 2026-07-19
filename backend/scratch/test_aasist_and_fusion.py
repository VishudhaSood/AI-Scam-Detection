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

    def test_evidence_fusion_weighted_math(self):
        """
        Test that evidence fusion calculates weighted combinations correctly.
        """
        # Let's say all metrics are at 0.50
        # Weights: trans(0.40) + deepfake(0.20) + heur(0.20) + rag(0.10) + verification(0.10)
        # combined = 0.50 * 0.40 + 0.50 * 0.20 + 0.50 * 0.20 + 0.50 * 0.10 + 0.50 * 0.10 = 0.50
        fused, breakdown = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=0.50,
            deepfake_prob=0.50,
            heuristic_risk=0.50,
            advisories_count=1, # rag_score = 0.5
            verification_verdict="NOT_YET_ANSWERED" # verification_score = 0.0
        )
        # Expected:
        # trans: 0.50 * 0.40 = 0.20
        # deepfake: 0.50 * 0.20 = 0.10
        # heur: 0.50 * 0.20 = 0.10
        # rag_score: 0.50 * 0.10 = 0.05
        # verification: 0.0 * 0.10 = 0.0
        # Total sum = 0.45
        # Normalized: 0.45
        # But wait, deepfake (0.5) is present, so fused = max(fused, transcript_risk) -> max(0.45, 0.50) = 0.50
        self.assertEqual(fused, 0.50)
        self.assertEqual(breakdown["transcript"], 0.50)
        self.assertEqual(breakdown["deepfake"], 0.50)
        self.assertEqual(breakdown["heuristics"], 0.50)
        self.assertEqual(breakdown["rag_match"], 0.50)
        self.assertEqual(breakdown["verification"], 0.0)

    def test_evidence_fusion_missing_deepfake(self):
        """
        Test that if AASIST is disabled or fails (deepfake_prob is None),
        the engine redistributes the weights correctly.
        """
        # Metrics: trans(0.50), deepfake(None), heur(0.50), rag_match(0.50), verification(0.0)
        # Active weights: trans(0.40), heur(0.20), rag(0.10), verif(0.10). Sum = 0.80
        # Weighted sum: 0.50*0.40 + 0.50*0.20 + 0.50*0.10 + 0.0*0.10 = 0.35
        # Normalized score: 0.35 / 0.80 = 0.4375 -> 0.44
        fused, breakdown = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=0.50,
            deepfake_prob=None,
            heuristic_risk=0.50,
            advisories_count=1,
            verification_verdict="N/A"
        )
        self.assertEqual(fused, 0.44)
        self.assertEqual(breakdown["deepfake"], 0.0)

    def test_rule_low_deepfake_cannot_reduce_risk(self):
        """
        Test Rule: A low deepfake score must NEVER reduce transcript-based scam risk.
        """
        # If transcript risk is 0.80, and deepfake is 0.0 (safe)
        # Even if weighted average is low, fused score must be >= 0.80.
        fused, _ = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=0.80,
            deepfake_prob=0.0,
            heuristic_risk=0.10,
            advisories_count=0,
            verification_verdict="PLAUSIBLE"
        )
        self.assertGreaterEqual(fused, 0.80)

    def test_rule_deepfake_cannot_trigger_danger_alone(self):
        """
        Test Rule: Deepfake probability should increase confidence but should never
        automatically classify a call as a scam (cross into DANGER >= 0.75) if content
        transcript risk and heuristics are low (< 0.40).
        """
        # E.g., transcript_risk = 0.1, heuristics = 0.1, but deepfake_prob = 0.99
        # Fused score must be capped at 0.74 (VERIFY state).
        fused, _ = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=0.10,
            deepfake_prob=0.99,
            heuristic_risk=0.10,
            advisories_count=0,
            verification_verdict="N/A"
        )
        # The fused score should remain below the 0.75 DANGER threshold
        self.assertLess(fused, 0.75)

if __name__ == "__main__":
    unittest.main()
