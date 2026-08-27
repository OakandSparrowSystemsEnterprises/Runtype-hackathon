import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("tenki_swarm.py")
SPEC = importlib.util.spec_from_file_location("tenki_swarm", MODULE_PATH)
tenki_swarm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tenki_swarm)


class TenkiSwarmContractTests(unittest.TestCase):
    def test_plan_never_grants_authority(self):
        plan = tenki_swarm.build_swarm_plan("sha256:demo")
        self.assertFalse(plan["authority"])
        self.assertGreaterEqual(len(plan["jobs"]), 3)
        self.assertTrue(all(job["authority"] is False for job in plan["jobs"]))

    def test_missing_live_endpoint_is_pending_not_fake_live(self):
        original = tenki_swarm.TENKI_STEWARD_URL
        tenki_swarm.TENKI_STEWARD_URL = ""
        try:
            result = tenki_swarm.run_tenki_swarm("sha256:demo")
        finally:
            tenki_swarm.TENKI_STEWARD_URL = original
        self.assertEqual(result["status"], "NEXT_PENDING")
        self.assertFalse(result["live"])
        self.assertFalse(result["authority"])

    def test_upstream_cannot_manufacture_authority(self):
        plan = tenki_swarm.build_swarm_plan("sha256:demo")
        with self.assertRaises(RuntimeError):
            tenki_swarm._normalize_worker_response(
                plan,
                {"authority": True, "workers": []},
                1.0,
            )

    def test_nested_worker_cannot_manufacture_token(self):
        plan = tenki_swarm.build_swarm_plan("sha256:demo")
        with self.assertRaises(RuntimeError):
            tenki_swarm._normalize_worker_response(
                plan,
                {
                    "authority": False,
                    "workers": [
                        {
                            "worker_id": "w1",
                            "result": {"token": "worker-issued-token"},
                        }
                    ],
                },
                1.0,
            )

    def test_nested_aggregate_cannot_manufacture_gatekeeper_verdict(self):
        plan = tenki_swarm.build_swarm_plan("sha256:demo")
        with self.assertRaises(RuntimeError):
            tenki_swarm._normalize_worker_response(
                plan,
                {
                    "authority": False,
                    "workers": [],
                    "aggregate": {
                        "claim": "derived-only",
                        "gatekeeper_verdict": "GREEN",
                    },
                },
                1.0,
            )

    def test_live_normalization_preserves_raw_payload(self):
        plan = tenki_swarm.build_swarm_plan("sha256:demo")
        payload = {
            "workers": [{"worker_id": "w1", "ok": True}],
            "aggregate": {"claim": "derived-only"},
            "authority": False,
        }
        result = tenki_swarm._normalize_worker_response(plan, payload, 12.5)
        self.assertEqual(result["status"], "LIVE")
        self.assertTrue(result["live"])
        self.assertFalse(result["authority"])
        self.assertEqual(result["raw"], payload)


if __name__ == "__main__":
    unittest.main()
