"""Tests for the LOCAL steward-wired evidence pipeline with the AIsa x
Mitosis sponsor plane ported in via scripts/integrate_sponsor_plane.py.

Skips itself (rather than failing) when the local evidence_pipeline.py is
not the steward-wired variant or has not been patched yet.
"""
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

STEWARD_WIRED = hasattr(evidence_pipeline, "run_deterministic_steward")
SPONSOR_PATCHED = hasattr(evidence_pipeline, "run_aisa_mitosis")


def healthy_arena(base):
    return {
        "ok": True,
        "cotal": {"ok": True, "status": "LIVE"},
        "estate": {"ok": True, "status": "LIVE"},
    }


def live_steward(artifact_ref, requested_effect, principal):
    return {
        "status": "LIVE",
        "implemented": True,
        "swarm_native": True,
        "authority": False,
        "state_hash": "s" * 64,
        "workers": [
            {
                "plane": "cotal",
                "status": "COMPLETED",
                "live": True,
                "authority": False,
            },
            {
                "plane": "tenki",
                "status": "COMPLETED",
                "live": True,
                "authority": False,
                "output": {"status": "LIVE", "live": True, "authority": False},
            },
        ],
    }


def partial_steward(artifact_ref, requested_effect, principal):
    result = live_steward(artifact_ref, requested_effect, principal)
    result["status"] = "PARTIAL"
    result["workers"][1]["status"] = "PENDING"
    result["workers"][1]["live"] = False
    result["workers"][1]["output"] = {
        "status": "NEXT_PENDING", "live": False, "authority": False,
    }
    return result


def pending_sponsor(artifact_ref, requested_effect, principal, target_url=None):
    return {
        "status": "NEXT_PENDING",
        "live": False,
        "implemented": True,
        "authority": False,
        "sponsor": "AIsa.ONE x Mitosis",
    }


@unittest.skipUnless(
    STEWARD_WIRED and SPONSOR_PATCHED,
    "requires the steward-wired evidence_pipeline patched with the sponsor plane "
    "(run scripts/integrate_sponsor_plane.py first)",
)
class StewardWiredSponsorPipelineTests(unittest.TestCase):
    def setUp(self):
        self.original_run_arena = evidence_pipeline.run_arena
        self.original_run_steward = evidence_pipeline.run_deterministic_steward
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
        evidence_pipeline.run_deterministic_steward = self.original_run_steward
        evidence_pipeline.run_aisa_mitosis = self.original_run_sponsor

    def test_identity_passed_to_steward_and_sponsor(self):
        observed = {}
        evidence_pipeline.run_arena = healthy_arena

        def run_steward(artifact_ref, requested_effect, principal):
            observed["steward"] = (artifact_ref, requested_effect, principal)
            return live_steward(artifact_ref, requested_effect, principal)

        def run_sponsor(artifact_ref, requested_effect, principal, target_url=None):
            observed["sponsor"] = (
                artifact_ref, requested_effect, principal, target_url
            )
            return pending_sponsor(artifact_ref, requested_effect, principal)

        evidence_pipeline.run_deterministic_steward = run_steward
        evidence_pipeline.run_aisa_mitosis = run_sponsor
        evidence_pipeline.run_progressive_evidence(self.base_demo)

        expected = (
            self.base_demo["artifact_ref"],
            self.base_demo["requested_effect"],
            self.base_demo["effect_principal"],
        )
        self.assertEqual(observed["steward"], expected)
        self.assertEqual(
            observed["sponsor"], expected + (self.base_demo["target_url"],)
        )

    def test_live_steward_passes_through_unchanged(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_deterministic_steward = live_steward
        evidence_pipeline.run_aisa_mitosis = pending_sponsor

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        steward = result["deterministic_steward"]
        self.assertEqual(steward["status"], "LIVE")
        self.assertTrue(steward["implemented"])
        self.assertFalse(steward["authority"])
        self.assertEqual(steward["state_hash"], "s" * 64)
        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertTrue(result["evidence_complete"])

    def test_partial_steward_status_is_preserved_verbatim(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_deterministic_steward = partial_steward
        evidence_pipeline.run_aisa_mitosis = pending_sponsor

        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertEqual(result["deterministic_steward"]["status"], "PARTIAL")
        self.assertTrue(result["cotal"]["ok"])
        self.assertFalse(result["evidence_complete"])
        self.assertEqual(
            result["sponsor"]["aisa_mitosis"]["status"], "NEXT_PENDING"
        )

    def test_sponsor_failure_never_touches_steward_or_core_evidence(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_deterministic_steward = live_steward

        def fail_sponsor(artifact_ref, requested_effect, principal, target_url=None):
            raise RuntimeError("sponsor plane unavailable")

        evidence_pipeline.run_aisa_mitosis = fail_sponsor
        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertEqual(result["deterministic_steward"]["status"], "LIVE")
        self.assertTrue(result["cotal"]["ok"])
        self.assertTrue(result["estate"]["ok"])
        self.assertTrue(result["evidence_complete"])
        sponsor = result["sponsor"]["aisa_mitosis"]
        self.assertEqual(sponsor["status"], "FAILED")
        self.assertFalse(sponsor["authority"])
        self.assertFalse(result["sponsor_evidence_live"])

    def test_steward_failure_is_isolated_and_sponsor_still_runs(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_aisa_mitosis = pending_sponsor

        def fail_steward(artifact_ref, requested_effect, principal):
            raise RuntimeError("steward unavailable")

        evidence_pipeline.run_deterministic_steward = fail_steward
        result = evidence_pipeline.run_progressive_evidence(self.base_demo)
        self.assertTrue(result["gatekeeper_verdict_preserved"])
        self.assertEqual(result["deterministic_steward"]["status"], "FAILED")
        self.assertFalse(result["deterministic_steward"]["authority"])
        self.assertEqual(
            result["sponsor"]["aisa_mitosis"]["status"], "NEXT_PENDING"
        )

    def test_sponsor_live_is_reported_without_gating_core(self):
        evidence_pipeline.run_arena = healthy_arena
        evidence_pipeline.run_deterministic_steward = live_steward
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
        self.assertTrue(result["evidence_complete"])


if __name__ == "__main__":
    unittest.main()
