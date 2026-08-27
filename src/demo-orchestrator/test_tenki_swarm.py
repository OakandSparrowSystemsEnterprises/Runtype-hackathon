import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("tenki_swarm.py")
SPEC = importlib.util.spec_from_file_location("tenki_swarm", MODULE_PATH)
tenki_swarm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tenki_swarm)

ARTIFACT_REF = "sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5"
LIVE_PAYLOAD = {
    "claim": {
        "artifact_ref": ARTIFACT_REF,
        "artifact_sha256": "5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5",
        "authority": False,
        "capacity_bits_per_s": 320.0,
        "claim_hash": "b36d8b524ea6db6639a36d834070474b71828e83f8d61c20e2de88dd353740ad",
        "compute_plane": "tenki",
        "kind": "goi_l0_boundary_capacity",
        "omega_res": 256,
        "principal": "agent-b",
        "requested_effect": "parent-shield.navigation",
        "role": "derived_claim_only",
        "tau_ms": 25.0,
    },
    "ok": True,
}


class TenkiSwarmContractTests(unittest.TestCase):
    def test_plan_never_grants_authority(self):
        plan = tenki_swarm.build_swarm_plan(ARTIFACT_REF)
        self.assertFalse(plan["authority"])
        self.assertGreaterEqual(len(plan["jobs"]), 3)
        self.assertTrue(all(job["authority"] is False for job in plan["jobs"]))

    def test_missing_live_endpoint_is_pending_not_fake_live(self):
        original_url = tenki_swarm.TENKI_STEWARD_URL
        original_capture = tenki_swarm.TENKI_CAPTURED_RESPONSE_JSON
        tenki_swarm.TENKI_STEWARD_URL = ""
        tenki_swarm.TENKI_CAPTURED_RESPONSE_JSON = ""
        try:
            result = tenki_swarm.run_tenki_swarm(ARTIFACT_REF)
        finally:
            tenki_swarm.TENKI_STEWARD_URL = original_url
            tenki_swarm.TENKI_CAPTURED_RESPONSE_JSON = original_capture
        self.assertEqual(result["status"], "NEXT_PENDING")
        self.assertFalse(result["live"])
        self.assertFalse(result["authority"])

    def test_upstream_cannot_manufacture_authority(self):
        plan = tenki_swarm.build_swarm_plan(ARTIFACT_REF)
        payload = {"ok": True, "claim": dict(LIVE_PAYLOAD["claim"], authority=True)}
        with self.assertRaises(RuntimeError):
            tenki_swarm._normalize_worker_response(plan, payload, 1.0)

    def test_nested_claim_cannot_manufacture_token(self):
        plan = tenki_swarm.build_swarm_plan(ARTIFACT_REF)
        claim = dict(LIVE_PAYLOAD["claim"])
        claim["details"] = {"token": "worker-issued-token"}
        with self.assertRaises(RuntimeError):
            tenki_swarm._normalize_worker_response(plan, {"ok": True, "claim": claim}, 1.0)

    def test_claim_artifact_must_match_governed_artifact(self):
        plan = tenki_swarm.build_swarm_plan(ARTIFACT_REF)
        claim = dict(LIVE_PAYLOAD["claim"], artifact_ref="sha256:" + "0" * 64)
        with self.assertRaises(RuntimeError):
            tenki_swarm._normalize_worker_response(plan, {"ok": True, "claim": claim}, 1.0)

    def test_live_normalization_preserves_exact_payload(self):
        plan = tenki_swarm.build_swarm_plan(ARTIFACT_REF)
        result = tenki_swarm._normalize_worker_response(plan, LIVE_PAYLOAD, 19.0)
        self.assertEqual(result["status"], "LIVE")
        self.assertTrue(result["live"])
        self.assertFalse(result["authority"])
        self.assertEqual(result["claim"], LIVE_PAYLOAD["claim"])
        self.assertEqual(result["raw"], LIVE_PAYLOAD)
        self.assertEqual(result["source"], "live_http")

    def test_captured_live_response_binds_exact_shape(self):
        original = tenki_swarm.TENKI_CAPTURED_RESPONSE_JSON
        tenki_swarm.TENKI_CAPTURED_RESPONSE_JSON = __import__("json").dumps(LIVE_PAYLOAD)
        try:
            result = tenki_swarm.run_tenki_swarm(ARTIFACT_REF)
        finally:
            tenki_swarm.TENKI_CAPTURED_RESPONSE_JSON = original
        self.assertEqual(result["status"], "LIVE")
        self.assertEqual(result["source"], "captured_live_response")
        self.assertEqual(result["raw"], LIVE_PAYLOAD)
        self.assertFalse(result["authority"])


if __name__ == "__main__":
    unittest.main()
