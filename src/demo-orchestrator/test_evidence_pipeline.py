import importlib.util
import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

MODULE_PATH = MODULE_DIR / "evidence_pipeline.py"
SPEC = importlib.util.spec_from_file_location("evidence_pipeline", MODULE_PATH)
evidence_pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence_pipeline)


class ProgressiveEvidenceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.original_run_arena = evidence_pipeline.run_arena
        self.original_run_tenki_swarm = evidence_pipeline.run_tenki_swarm
        self.base_demo = {
            "ok": True,
            "run_id": "demo-run",
            "artifact_ref": "sha256:" + ("a" * 64),
            "gatekeeper": {"formal": "permit", "execution": "allowed"},
        }

    def tearDown(self):
        evidence_pipeline.run_arena = self.original_run_arena
        evidence_pipeline.run_tenki_swarm = self.original_run_tenki_swarm

    def test_pending_tenki_preserves_healthy_cotal_and_estate(self):
        evidence_pipeline.run_arena = lambda base: {
            "ok": True,
            "cotal": {"ok": True, "status": "LIVE"},
            "estate": {"ok": True, "status": "LIVE"},
        }
        evidence_pipeline.run_tenki_swarm = lambda artifact_ref: {
            "status": "NEXT_PENDING",
            "live": False,
            "authority": False,
        }

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)

        self.assertTrue(result["ok"])
        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertTrue(result["cotal"]["ok"])
        self.assertTrue(result["estate"]["ok"])
        self.assertEqual(result["tenki"]["status"], "NEXT_PENDING")
        self.assertEqual(
            result["deterministic_steward"]["status"],
            "IMPLEMENTATION_PENDING",
        )

    def test_tenki_failure_does_not_suppress_other_evidence(self):
        evidence_pipeline.run_arena = lambda base: {
            "ok": True,
            "cotal": {"ok": True, "status": "LIVE"},
            "estate": {"ok": True, "status": "LIVE"},
        }

        def fail_tenki(artifact_ref):
            raise RuntimeError("tenki unavailable")

        evidence_pipeline.run_tenki_swarm = fail_tenki

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)

        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertTrue(result["cotal"]["ok"])
        self.assertTrue(result["estate"]["ok"])
        self.assertEqual(result["tenki"]["status"], "FAILED")
        self.assertFalse(result["tenki"]["authority"])
        self.assertFalse(result["tenki"]["live"])

    def test_cotal_estate_failure_does_not_suppress_tenki(self):
        def fail_arena(base):
            raise RuntimeError("supporting arena unavailable")

        evidence_pipeline.run_arena = fail_arena
        evidence_pipeline.run_tenki_swarm = lambda artifact_ref: {
            "status": "LIVE",
            "live": True,
            "authority": False,
            "workers": [{"worker_id": "w1", "ok": True}],
            "aggregate": {"claim": "derived-only"},
        }

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)

        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertEqual(result["cotal"]["status"], "FAILED")
        self.assertEqual(result["estate"]["status"], "FAILED")
        self.assertEqual(result["tenki"]["status"], "LIVE")
        self.assertTrue(result["tenki"]["live"])
        self.assertFalse(result["tenki"]["authority"])
        self.assertEqual(result["deterministic_steward"]["status"], "LIVE")

    def test_missing_artifact_ref_fails_before_supporting_work(self):
        with self.assertRaises(RuntimeError):
            evidence_pipeline.run_progressive_evidence({"ok": True})


if __name__ == "__main__":
    unittest.main()
