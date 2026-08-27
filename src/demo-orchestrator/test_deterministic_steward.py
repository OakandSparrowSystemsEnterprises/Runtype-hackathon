import time
import unittest
from unittest.mock import patch

import deterministic_steward as steward


ARTIFACT = "sha256:" + "a" * 64
EFFECT = "parent-shield.navigation"
PRINCIPAL = "agent-b"


class DeterministicStewardTests(unittest.TestCase):
    def test_plan_is_stable_for_same_governed_inputs(self):
        first = steward.build_plan(ARTIFACT, EFFECT, PRINCIPAL)
        second = steward.build_plan(ARTIFACT, EFFECT, PRINCIPAL)
        self.assertEqual(first, second)
        self.assertFalse(first["authority"])
        self.assertEqual(len(first["workers"]), 2)

    def test_completion_order_does_not_change_state_hash(self):
        def cotal_fast(_artifact):
            return {"ok": True, "swarm_live": True}

        def tenki_slow(_artifact, _effect, _principal):
            time.sleep(0.02)
            return {"status": "LIVE", "live": True, "authority": False}

        with patch.object(steward, "run_cotal_probe", cotal_fast), patch.object(
            steward, "run_tenki_swarm", tenki_slow
        ):
            first = steward.run_deterministic_steward(ARTIFACT, EFFECT, PRINCIPAL)

        def cotal_slow(_artifact):
            time.sleep(0.02)
            return {"ok": True, "swarm_live": True}

        def tenki_fast(_artifact, _effect, _principal):
            return {"status": "LIVE", "live": True, "authority": False}

        with patch.object(steward, "run_cotal_probe", cotal_slow), patch.object(
            steward, "run_tenki_swarm", tenki_fast
        ):
            second = steward.run_deterministic_steward(ARTIFACT, EFFECT, PRINCIPAL)

        self.assertEqual(first["plan"]["plan_id"], second["plan"]["plan_id"])
        self.assertEqual(first["state_hash"], second["state_hash"])
        self.assertEqual(
            [item["worker_id"] for item in first["workers"]],
            sorted(item["worker_id"] for item in first["workers"]),
        )

    def test_worker_failure_is_isolated(self):
        def cotal_ok(_artifact):
            return {"ok": True, "swarm_live": True}

        def tenki_fail(_artifact, _effect, _principal):
            raise RuntimeError("worker unavailable")

        with patch.object(steward, "run_cotal_probe", cotal_ok), patch.object(
            steward, "run_tenki_swarm", tenki_fail
        ):
            result = steward.run_deterministic_steward(ARTIFACT, EFFECT, PRINCIPAL)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["live_workers"], 1)
        self.assertEqual(result["failed_workers"], 1)
        self.assertTrue(result["failure_isolated"])
        self.assertFalse(result["authority"])


if __name__ == "__main__":
    unittest.main()
