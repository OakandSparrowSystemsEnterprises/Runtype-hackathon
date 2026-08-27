import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("diagnose_action_edge.py")
SPEC = importlib.util.spec_from_file_location("diagnose_action_edge", MODULE_PATH)
diagnose = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnose)


def classify(*, upstream_ok=True, signed_status="SKIPPED", signed_body=None):
    action_upstream_status = 200 if upstream_ok else 503
    action_upstream_body = {
        "reachable_from_action_edge": upstream_ok,
        "parent_shield_mounted": upstream_ok,
        "runtime_identity_proven": False,
    }
    return diagnose.classify_summary(
        200,
        action_upstream_status,
        action_upstream_body,
        401,
        {"error": "missing_agent_auth"},
        200,
        True,
        401,
        {"error": "missing_agent_auth"},
        signed_status,
        signed_body or {},
    )


class ActionEdgeDiagnosisTests(unittest.TestCase):
    def test_ready_when_all_unsigned_boundaries_pass(self):
        result = classify()
        self.assertEqual(result["status"], "READY_FOR_SIGNED_PROBE")
        self.assertEqual(result["boundary"], "signed_action")

    def test_action_edge_namespace_failure_is_isolated(self):
        result = classify(upstream_ok=False)
        self.assertEqual(result["status"], "REPRODUCED")
        self.assertEqual(result["boundary"], "action_edge_to_gatekeeper")

    def test_signed_unreachable_is_classified_without_secret_material(self):
        result = classify(
            signed_status=502,
            signed_body={
                "error": "gatekeeper_unreachable",
                "upstream_stage": "evaluate",
                "error_class": "ConnectionRefusedError",
                "upstream_latency_ms": 3.2,
            },
        )
        self.assertEqual(result["status"], "REPRODUCED")
        self.assertEqual(result["boundary"], "action_edge_signed_gatekeeper_call")
        self.assertEqual(result["error"], "gatekeeper_unreachable")
        self.assertNotIn("secret", result)

    def test_signed_invalid_response_is_distinct_from_unreachable(self):
        result = classify(
            signed_status=502,
            signed_body={
                "error": "gatekeeper_invalid_response",
                "upstream_stage": "decode_response",
                "upstream_latency_ms": 21.4,
            },
        )
        self.assertEqual(result["status"], "REPRODUCED")
        self.assertEqual(result["error"], "gatekeeper_invalid_response")
        self.assertIn("could not decode as JSON", result["reason"])

    def test_non_502_signed_result_does_not_claim_fix(self):
        result = classify(
            signed_status=200,
            signed_body={"gatekeeper": {"formal": "permit"}},
        )
        self.assertEqual(result["status"], "SIGNED_PROBE_COMPLETED")
        self.assertEqual(result["signed_status"], 200)
        self.assertNotEqual(result.get("status"), "FIXED")


if __name__ == "__main__":
    unittest.main()
