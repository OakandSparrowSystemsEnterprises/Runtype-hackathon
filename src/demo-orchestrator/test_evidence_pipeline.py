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
        self.original_run_aisa_mitosis_evidence = evidence_pipeline.run_aisa_mitosis_evidence
        self.base_demo = {
            "ok": True,
            "run_id": "demo-run",
            "artifact_ref": "sha256:" + ("a" * 64),
            "requested_effect": "parent-shield.navigation",
            "effect_principal": "agent-b",
            "gatekeeper": {"formal": "permit", "execution": "allowed"},
        }
        evidence_pipeline.run_aisa_mitosis_evidence = lambda: {
            "status": "PENDING",
            "live": False,
            "authority": False,
            "provider": "AIsa.ONE x Mitosis",
            "reason": "credentials not configured",
        }

    def tearDown(self):
        evidence_pipeline.run_arena = self.original_run_arena
        evidence_pipeline.run_tenki_swarm = self.original_run_tenki_swarm
        evidence_pipeline.run_aisa_mitosis_evidence = self.original_run_aisa_mitosis_evidence

    def test_current_run_identity_is_passed_to_tenki(self):
        observed = {}
        evidence_pipeline.run_arena = lambda base: {
            "ok": True,
            "cotal": {"ok": True, "status": "LIVE"},
            "estate": {"ok": True, "status": "LIVE"},
        }

        def run_tenki(artifact_ref, requested_effect, principal):
            observed.update({
                "artifact_ref": artifact_ref,
                "requested_effect": requested_effect,
                "principal": principal,
            })
            return {"status": "LIVE", "live": True, "authority": False}

        evidence_pipeline.run_tenki_swarm = run_tenki
        evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertEqual(observed, {
            "artifact_ref": self.base_demo["artifact_ref"],
            "requested_effect": self.base_demo["requested_effect"],
            "principal": self.base_demo["effect_principal"],
        })

    def test_pending_tenki_preserves_healthy_cotal_estate_and_sponsor_state(self):
        evidence_pipeline.run_arena = lambda base: {
            "ok": True,
            "cotal": {"ok": True, "status": "LIVE"},
            "estate": {"ok": True, "status": "LIVE"},
        }
        evidence_pipeline.run_tenki_swarm = lambda artifact_ref, effect, principal: {
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
        self.assertEqual(result["sponsors"]["aisa_mitosis"]["status"], "PENDING")
        self.assertFalse(result["sponsors"]["aisa_mitosis_live"])
        self.assertEqual(result["deterministic_steward"]["status"], "IMPLEMENTATION_PENDING")

    def test_tenki_failure_does_not_suppress_other_evidence(self):
        evidence_pipeline.run_arena = lambda base: {
            "ok": True,
            "cotal": {"ok": True, "status": "LIVE"},
            "estate": {"ok": True, "status": "LIVE"},
        }

        def fail_tenki(artifact_ref, effect, principal):
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
        evidence_pipeline.run_arena = lambda base: (_ for _ in ()).throw(
            RuntimeError("supporting arena unavailable")
        )
        evidence_pipeline.run_tenki_swarm = lambda artifact_ref, effect, principal: {
            "status": "LIVE",
            "live": True,
            "authority": False,
            "claim": {"role": "derived_claim_only"},
        }

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertEqual(result["cotal"]["status"], "FAILED")
        self.assertEqual(result["estate"]["status"], "FAILED")
        self.assertEqual(result["tenki"]["status"], "LIVE")
        self.assertTrue(result["tenki"]["live"])
        self.assertFalse(result["tenki"]["authority"])
        self.assertEqual(result["deterministic_steward"]["status"], "IMPLEMENTATION_PENDING")

    def test_live_sponsor_is_non_authoritative_and_does_not_change_core_completeness(self):
        evidence_pipeline.run_arena = lambda base: {
            "ok": True,
            "cotal": {"ok": True, "status": "LIVE"},
            "estate": {"ok": True, "status": "LIVE"},
        }
        evidence_pipeline.run_tenki_swarm = lambda artifact_ref, effect, principal: {
            "status": "LIVE",
            "live": True,
            "authority": False,
        }
        evidence_pipeline.run_aisa_mitosis_evidence = lambda: {
            "status": "LIVE",
            "live": True,
            "authority": False,
            "provider": "AIsa.ONE x Mitosis",
        }

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["evidence_complete"])
        self.assertTrue(result["sponsors"]["aisa_mitosis_live"])
        self.assertFalse(result["sponsors"]["aisa_mitosis"]["authority"])
        self.assertTrue(result["gatekeeper_verdict_preserved"])

    def test_sponsor_failure_is_isolated_from_gatekeeper_and_tenki(self):
        evidence_pipeline.run_arena = lambda base: {
            "ok": True,
            "cotal": {"ok": True, "status": "LIVE"},
            "estate": {"ok": True, "status": "LIVE"},
        }
        evidence_pipeline.run_tenki_swarm = lambda artifact_ref, effect, principal: {
            "status": "LIVE",
            "live": True,
            "authority": False,
        }
        evidence_pipeline.run_aisa_mitosis_evidence = lambda: (_ for _ in ()).throw(
            RuntimeError("sponsor unavailable")
        )

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertTrue(result["tenki"]["live"])
        self.assertEqual(result["sponsors"]["aisa_mitosis"]["status"], "FAILED")
        self.assertFalse(result["sponsors"]["aisa_mitosis"]["authority"])
        self.assertFalse(result["sponsors"]["aisa_mitosis_live"])

    def test_missing_current_run_binding_fails_before_supporting_work(self):
        for missing in ("artifact_ref", "requested_effect", "effect_principal"):
            bad = dict(self.base_demo)
            bad.pop(missing)
            with self.assertRaises(RuntimeError):
                evidence_pipeline.run_progressive_evidence(bad)


if __name__ == "__main__":
    unittest.main()
