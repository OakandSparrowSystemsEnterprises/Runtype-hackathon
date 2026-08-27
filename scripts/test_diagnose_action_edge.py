import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("diagnose_action_edge.py")
SPEC = importlib.util.spec_from_file_location("diagnose_action_edge", MODULE_PATH)
diagnose = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnose)


def classify(
    *,
    action_health_status=200,
    upstream_ok=True,
    direct_unsigned_status=401,
    direct_unsigned_body=None,
    gatekeeper_status=200,
    gatekeeper_mount_ok=True,
    public_unsigned_status=401,
    public_unsigned_body=None,
    signed_status="SKIPPED",
    signed_body=None,
):
    action_upstream_status = 200 if upstream_ok else 503
    action_upstream_body = {
        "reachable_from_action_edge": upstream_ok,
        "parent_shield_mounted": upstream_ok,
        "runtime_identity_proven": False,
    }
    return diagnose.classify_summary(
        action_health_status,
        action_upstream_status,
        action_upstream_body,
        direct_unsigned_status,
        direct_unsigned_body or {"error": "missing_agent_auth"},
        gatekeeper_status,
        gatekeeper_mount_ok,
        public_unsigned_status,
        public_unsigned_body or {"error": "missing_agent_auth"},
        signed_status,
        signed_body or {},
    )


class ActionEdgeDiagnosisTests(unittest.TestCase):
    def test_ready_when_all_unsigned_boundaries_pass(self):
        result = classify()
        self.assertEqual(result["status"], "READY_FOR_SIGNED_PROBE")
        self.assertEqual(result["boundary"], "signed_action")

    def test_action_edge_process_failure_is_isolated(self):
        result = classify(action_health_status=503)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["boundary"], "action_edge_process")

    def test_direct_unsigned_boundary_failure_is_isolated(self):
        result = classify(
            direct_unsigned_status=500,
            direct_unsigned_body={"error": "unexpected"},
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["boundary"], "action_edge_direct_post")

    def test_public_edge_failure_is_isolated(self):
        result = classify(
            public_unsigned_status=502,
            public_unsigned_body={"error": "bad_gateway"},
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["boundary"], "public_edge_to_action_edge")

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

    def test_signed_timeout_is_distinct_from_other_gatekeeper_failures(self):
        result = classify(
            signed_status=504,
            signed_body={
                "error": "gatekeeper_timeout",
                "upstream_stage": "evaluate",
                "upstream_latency_ms": 15000.0,
            },
        )
        self.assertEqual(result["status"], "REPRODUCED")
        self.assertEqual(result["boundary"], "action_edge_signed_gatekeeper_call")
        self.assertEqual(result["error"], "gatekeeper_timeout")
        self.assertIn("exceeded", result["reason"])

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
