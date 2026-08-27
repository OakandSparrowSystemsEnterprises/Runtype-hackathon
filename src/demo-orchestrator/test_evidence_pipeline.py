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


def healthy_arena(base):
    return {
        "ok": True,
        "cotal": {"ok": True, "status": "LIVE"},
        "estate": {"ok": True, "status": "LIVE"},
    }


def live_tenki(artifact_ref, requested_effect, principal):
    return {"status": "LIVE", "live": True, "authority": False}


def pending_sponsor(artifact_ref, requested_effect, principal, target_url=None):
    return {
        "status": "NEXT_PENDING",
        "live": False,
        "implemented": True,
        "authority": False,
        "sponsor": "AIsa.ONE x Mitosis",
    }


class ProgressiveEvidenceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.original_run_arena = evidence_pipeline.run_arena
        self.original_run_tenki = evidence_pipeline.run_tenki_swarm
        self.original_run_sponsor = evidence_pipeline.run_aisa_mitosis
        self.base_demo = {
            "ok": True,
            "run_id": "demo-run",
            "artifact_ref": "sha256:" + ("a" * 64),
            "requested_effect": "parent-shield.navigation",
            "effect_principal": "agent-b",
            "target_url": "https://en.wikipedia.org/wiki/Math",
            "gatekeeper": {"formal": "permit", "execution": "allowed"},
        }

    def tearDown(self):
        evidence_pipeline.run_arena = self.original_run_arena
        evidence_pipeline.run_tenki_swarm = self.original_run_tenki
        evidence_pipeline.run_aisa_mitosis = self.original_run_sponsor

    def test_current_run_identity_is_passed_to_tenki_and_sponsor(self):
        observed = {}
        evidence_pipeline.run_arena = healthy_arena

        def run_tenki(artifact_ref, requested_effect, principal):
            observed["tenki"] = (artifact_ref, requested_effect, principal)
            return live_tenki(artifact_ref, requested_effect, principal)

        def run_sponsor(artifact_ref, requested_effect, principal, target_url=None):
            observed["sponsor"] = (
                artifact_ref, requested_effect, principal, target_url
            )
            return pending_sponsor(artifact_ref, requested_effect, principal)

        evidence_pipeline.run_tenki_swarm = run_tenki
        evidence_pipeline.run_aisa_mitosis = run_sponsor
        evidence_pipeline.run_progressive_evidence(self.base_demo)

        expected = (
            self.base_demo["artifact_ref"],
            self.base_demo["requested_effect"],
            self.base_demo["effect_principal"],
        )
        self.assertEqual(observed["tenki"], expected)
        self.assertEqual(
            observed["sponsor"], expected + (self.base_demo["target_url"],)
        )

    def test_steward_is_reported_implementation_pending(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_tenki_swarm = live_tenki
        evidence_pipeline.run_aisa_mitosis = pending_sponsor

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        steward = result["deterministic_steward"]
        self.assertEqual(steward["status"], "IMPLEMENTATION_PENDING")
        self.assertFalse(steward["implemented"])
        self.assertFalse(steward["authority"])

    def test_pending_sponsor_does_not_gate_core_evidence(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_tenki_swarm = live_tenki
        evidence_pipeline.run_aisa_mitosis = pending_sponsor

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["ok"])
        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertTrue(result["evidence_complete"])
        self.assertFalse(result["sponsor_evidence_live"])
        self.assertEqual(
            result["sponsor"]["aisa_mitosis"]["status"], "NEXT_PENDING"
        )

    def test_sponsor_failure_does_not_suppress_other_evidence(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_tenki_swarm = live_tenki

        def fail_sponsor(artifact_ref, requested_effect, principal, target_url=None):
            raise RuntimeError("sponsor plane unavailable")

        evidence_pipeline.run_aisa_mitosis = fail_sponsor
        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["ok"])
        self.assertTrue(result["cotal"]["ok"])
        self.assertTrue(result["estate"]["ok"])
        self.assertTrue(result["evidence_complete"])
        sponsor = result["sponsor"]["aisa_mitosis"]
        self.assertEqual(sponsor["status"], "FAILED")
        self.assertFalse(sponsor["authority"])
        self.assertFalse(result["sponsor_evidence_live"])

    def test_tenki_failure_does_not_suppress_sponsor_or_arena(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_aisa_mitosis = pending_sponsor

        def fail_tenki(artifact_ref, requested_effect, principal):
            raise RuntimeError("tenki unavailable")

        evidence_pipeline.run_tenki_swarm = fail_tenki
        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertTrue(result["cotal"]["ok"])
        self.assertEqual(result["tenki"]["status"], "FAILED")
        self.assertFalse(result["tenki"]["authority"])
        self.assertFalse(result["evidence_complete"])
        self.assertEqual(
            result["sponsor"]["aisa_mitosis"]["status"], "NEXT_PENDING"
        )

    def test_arena_failure_does_not_suppress_tenki_or_sponsor(self):
        def fail_arena(base):
            raise RuntimeError("supporting arena unavailable")

        evidence_pipeline.run_arena = fail_arena
        evidence_pipeline.run_tenki_swarm = live_tenki
        evidence_pipeline.run_aisa_mitosis = pending_sponsor

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertEqual(result["cotal"]["status"], "FAILED")
        self.assertEqual(result["estate"]["status"], "FAILED")
        self.assertEqual(result["tenki"]["status"], "LIVE")
        self.assertFalse(result["evidence_complete"])

    def test_sponsor_live_is_reported(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_tenki_swarm = live_tenki
        evidence_pipeline.run_aisa_mitosis = (
            lambda artifact_ref, requested_effect, principal, target_url=None: {
                "status": "LIVE",
                "live": True,
                "authority": False,
                "sponsor": "AIsa.ONE x Mitosis",
                "claim_hash": "c" * 64,
            }
        )

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["sponsor_evidence_live"])
        self.assertEqual(result["sponsor"]["aisa_mitosis"]["status"], "LIVE")

    def test_missing_current_run_binding_fails_before_supporting_work(self):
        for missing in ("artifact_ref", "requested_effect", "effect_principal"):
            bad = dict(self.base_demo)
            bad.pop(missing)
            with self.assertRaises(RuntimeError):
                evidence_pipeline.run_progressive_evidence(bad)


if __name__ == "__main__":
    unittest.main()
