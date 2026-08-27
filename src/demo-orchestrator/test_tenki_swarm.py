import importlib.util
import os
import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

MODULE_PATH = MODULE_DIR / "tenki_swarm.py"
SPEC = importlib.util.spec_from_file_location("tenki_swarm", MODULE_PATH)
tenki_swarm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tenki_swarm)

ARTIFACT = "sha256:" + ("a" * 64)
EFFECT = "parent-shield.navigation"
PRINCIPAL = "agent-b"

ENV_KEYS = ("TENKI_DERIVE_URLS", "TENKI_DERIVE_URL", "TENKI_STEWARD_URL")


def plan():
    return tenki_swarm.build_swarm_plan(ARTIFACT, EFFECT, PRINCIPAL)


def valid_payload(current_plan, claim_hash="h" * 64):
    return {
        "ok": True,
        "claim": {
            "authority": False,
            "artifact_ref": current_plan["artifact_ref"],
            "artifact_sha256": current_plan["artifact_ref"].split(":", 1)[1],
            "requested_effect": current_plan["requested_effect"],
            "principal": current_plan["principal"],
            "compute_plane": "tenki",
            "role": "derived_claim_only",
            "claim_hash": claim_hash,
        },
    }


class TenkiSwarmContractTests(unittest.TestCase):
    def setUp(self):
        self.saved_env = {key: os.environ.pop(key, None) for key in ENV_KEYS}
        self.saved_width = tenki_swarm.TENKI_SWARM_WIDTH
        self.saved_run_replica = tenki_swarm._run_replica

    def tearDown(self):
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        tenki_swarm.TENKI_SWARM_WIDTH = self.saved_width
        tenki_swarm._run_replica = self.saved_run_replica

    def test_claim_artifact_must_match_current_governed_artifact(self):
        payload = valid_payload(plan())
        payload["claim"]["artifact_ref"] = "sha256:" + ("b" * 64)
        with self.assertRaises(RuntimeError):
            tenki_swarm._validate_claim(plan(), payload)

    def test_claim_digest_must_match_current_governed_artifact(self):
        payload = valid_payload(plan())
        payload["claim"]["artifact_sha256"] = "b" * 64
        with self.assertRaises(RuntimeError):
            tenki_swarm._validate_claim(plan(), payload)

    def test_claim_effect_must_match_current_governed_effect(self):
        payload = valid_payload(plan())
        payload["claim"]["requested_effect"] = "other.effect"
        with self.assertRaises(RuntimeError):
            tenki_swarm._validate_claim(plan(), payload)

    def test_claim_principal_must_match_current_principal(self):
        payload = valid_payload(plan())
        payload["claim"]["principal"] = "agent-a"
        with self.assertRaises(RuntimeError):
            tenki_swarm._validate_claim(plan(), payload)

    def test_claim_must_remain_derived_claim_only(self):
        payload = valid_payload(plan())
        payload["claim"]["role"] = "authority_source"
        with self.assertRaises(RuntimeError):
            tenki_swarm._validate_claim(plan(), payload)

    def test_nested_response_cannot_manufacture_authority(self):
        for field in ("authority", "permit", "capability", "token", "gatekeeper_verdict"):
            payload = valid_payload(plan())
            payload["nested"] = {"deep": [{field: "granted"}]}
            with self.assertRaises(RuntimeError):
                tenki_swarm._validate_claim(plan(), payload)

    def test_missing_runtime_endpoints_is_pending_not_fake_live(self):
        result = tenki_swarm.run_tenki_swarm(ARTIFACT, EFFECT, PRINCIPAL)
        self.assertEqual(result["status"], "NEXT_PENDING")
        self.assertFalse(result["live"])
        self.assertFalse(result["authority"])
        self.assertEqual(result["configured_endpoint_count"], 0)
        self.assertTrue(all(w["status"] == "PENDING" for w in result["workers"]))
        self.assertFalse(result["aggregate"]["consensus"])

    def test_two_matching_replicas_reach_consensus_live(self):
        os.environ["TENKI_DERIVE_URLS"] = "https://r0.test/derive,https://r1.test/derive"
        tenki_swarm.TENKI_SWARM_WIDTH = 2

        def fake_replica(spec, endpoint, current_plan, request_body):
            claim = valid_payload(current_plan)["claim"]
            return {
                **spec,
                "status": "COMPLETED",
                "live": True,
                "authority": False,
                "endpoint_configured": True,
                "claim": claim,
                "claim_hash": claim["claim_hash"],
                "error": None,
                "elapsed_ms": 1.0,
            }

        tenki_swarm._run_replica = fake_replica
        result = tenki_swarm.run_tenki_swarm(ARTIFACT, EFFECT, PRINCIPAL)
        self.assertEqual(result["status"], "LIVE")
        self.assertTrue(result["live"])
        self.assertTrue(result["aggregate"]["consensus"])
        self.assertEqual(result["aggregate"]["completed"], 2)
        self.assertFalse(result["authority"])

    def test_divergent_replica_claims_do_not_reach_consensus(self):
        os.environ["TENKI_DERIVE_URLS"] = "https://r0.test/derive,https://r1.test/derive"
        tenki_swarm.TENKI_SWARM_WIDTH = 2

        def fake_replica(spec, endpoint, current_plan, request_body):
            claim_hash = ("x" if spec["replica_index"] == 0 else "y") * 64
            claim = valid_payload(current_plan, claim_hash)["claim"]
            return {
                **spec,
                "status": "COMPLETED",
                "live": True,
                "authority": False,
                "endpoint_configured": True,
                "claim": claim,
                "claim_hash": claim_hash,
                "error": None,
                "elapsed_ms": 1.0,
            }

        tenki_swarm._run_replica = fake_replica
        result = tenki_swarm.run_tenki_swarm(ARTIFACT, EFFECT, PRINCIPAL)
        self.assertNotEqual(result["status"], "LIVE")
        self.assertFalse(result["aggregate"]["consensus"])
        self.assertIsNone(result["aggregate"]["consensus_claim_hash"])


if __name__ == "__main__":
    unittest.main()
