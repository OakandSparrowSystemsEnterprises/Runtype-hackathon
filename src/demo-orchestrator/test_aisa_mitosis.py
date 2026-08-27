import importlib.util
import json
import os
import pathlib
import sys
import unittest
import urllib.error

MODULE_DIR = pathlib.Path(__file__).parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

MODULE_PATH = MODULE_DIR / "aisa_mitosis.py"
SPEC = importlib.util.spec_from_file_location("aisa_mitosis", MODULE_PATH)
aisa_mitosis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aisa_mitosis)

ENV_KEYS = (
    "AISA_API_BASE",
    "AISA_API_KEY",
    "AISA_CAPABILITY_PATH",
    "AISA_MODEL",
    "AISA_AUTH_HEADER",
    "AISA_AUTH_SCHEME",
    "AISA_TIMEOUT",
    "MITOSIS_MCP_URL",
    "MITOSIS_API_KEY",
    "MITOSIS_TIMEOUT",
)

ARTIFACT_REF = "sha256:" + ("a" * 64)
EFFECT = "parent-shield.navigation"
PRINCIPAL = "agent-b"
TARGET = "https://en.wikipedia.org/wiki/Math"


def openai_style_response(content):
    return json.dumps({
        "choices": [{"message": {"role": "assistant", "content": content}}],
    })


class AisaMitosisSponsorPlaneTests(unittest.TestCase):
    def setUp(self):
        self.saved_env = {key: os.environ.pop(key, None) for key in ENV_KEYS}
        self.original_http = aisa_mitosis._http_json

    def tearDown(self):
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        aisa_mitosis._http_json = self.original_http

    def configure_aisa(self):
        os.environ["AISA_API_BASE"] = "https://aisa.test"
        os.environ["AISA_API_KEY"] = "aisa-secret-key"
        os.environ["AISA_MODEL"] = "demo-model"

    def configure_mitosis(self):
        os.environ["MITOSIS_MCP_URL"] = "https://mitosis.test/api/mcp"
        os.environ["MITOSIS_API_KEY"] = "mitosis-secret-key"

    def test_unconfigured_reports_pending_and_never_calls_network(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("network must not be touched when unconfigured")

        aisa_mitosis._http_json = forbidden
        result = aisa_mitosis.run_aisa_mitosis(ARTIFACT_REF, EFFECT, PRINCIPAL, TARGET)
        self.assertEqual(result["status"], "NEXT_PENDING")
        self.assertFalse(result["live"])
        self.assertFalse(result["authority"])
        self.assertEqual(result["aisa"]["status"], "PENDING")
        self.assertEqual(result["mitosis"]["status"], "PENDING")
        self.assertIsNone(result["claim"])
        self.assertTrue(result["implemented"])

    def test_claim_binds_current_governed_run_and_is_deterministic(self):
        self.configure_aisa()

        def fake_http(url, body, headers, timeout):
            self.assertTrue(url.startswith("https://aisa.test"))
            self.assertEqual(headers["Authorization"], "Bearer aisa-secret-key")
            return 200, openai_style_response('{"summary":"math reference"}'), {}

        aisa_mitosis._http_json = fake_http
        first = aisa_mitosis.run_aisa_mitosis(ARTIFACT_REF, EFFECT, PRINCIPAL, TARGET)
        second = aisa_mitosis.run_aisa_mitosis(ARTIFACT_REF, EFFECT, PRINCIPAL, TARGET)

        self.assertEqual(first["status"], "PARTIAL")
        claim = first["claim"]
        self.assertEqual(claim["artifact_ref"], ARTIFACT_REF)
        self.assertEqual(claim["artifact_sha256"], "a" * 64)
        self.assertEqual(claim["requested_effect"], EFFECT)
        self.assertEqual(claim["principal"], PRINCIPAL)
        self.assertEqual(claim["target_url"], TARGET)
        self.assertIs(claim["authority"], False)
        self.assertEqual(claim["role"], "capability_evidence_only")
        self.assertEqual(first["claim_hash"], second["claim_hash"])
        self.assertEqual(first["state_hash"], second["state_hash"])
        self.assertEqual(first["mitosis"]["status"], "PENDING")

    def test_authority_assertion_in_aisa_response_is_rejected(self):
        self.configure_aisa()

        def fake_http(url, body, headers, timeout):
            return 200, json.dumps({
                "capability": "granted",
                "choices": [{"message": {"content": "ok"}}],
            }), {}

        aisa_mitosis._http_json = fake_http
        result = aisa_mitosis.run_aisa_mitosis(ARTIFACT_REF, EFFECT, PRINCIPAL, TARGET)
        self.assertEqual(result["aisa"]["status"], "FAILED")
        self.assertIn("authority", result["aisa"]["error"])
        self.assertIsNone(result["claim"])
        self.assertEqual(result["status"], "FAILED")
        self.assertFalse(result["authority"])

    def test_full_pipeline_live_with_mitosis_packaging(self):
        self.configure_aisa()
        self.configure_mitosis()
        calls = []

        def fake_http(url, body, headers, timeout):
            calls.append((url, body))
            if url.startswith("https://aisa.test"):
                return 200, openai_style_response("evidence text"), {}
            method = body.get("method")
            if method == "initialize":
                return 200, json.dumps({
                    "jsonrpc": "2.0", "id": 1,
                    "result": {"serverInfo": {"name": "mitosis"}},
                }), {"Mcp-Session-Id": "sess-1"}
            if method == "notifications/initialized":
                self.assertEqual(headers.get("Mcp-Session-Id"), "sess-1")
                return 202, "", {}
            if method == "tools/call":
                self.assertEqual(body["params"]["name"], "cortex_remember")
                self.assertIn("authority=false", body["params"]["arguments"]["text"])
                return 200, json.dumps({
                    "jsonrpc": "2.0", "id": 2,
                    "result": {"content": [{"type": "text", "text": "remembered"}]},
                }), {}
            raise AssertionError(f"unexpected MCP method {method}")

        aisa_mitosis._http_json = fake_http
        result = aisa_mitosis.run_aisa_mitosis(ARTIFACT_REF, EFFECT, PRINCIPAL, TARGET)

        self.assertEqual(result["status"], "LIVE")
        self.assertTrue(result["live"])
        self.assertFalse(result["authority"])
        self.assertEqual(result["mitosis"]["status"], "COMPLETED")
        self.assertEqual(
            result["mitosis"]["packaged_claim_hash"], result["claim_hash"]
        )
        self.assertEqual(result["mitosis"]["memory_excerpt"], "remembered")
        serialized = json.dumps(result)
        self.assertNotIn("aisa-secret-key", serialized)
        self.assertNotIn("mitosis-secret-key", serialized)

    def test_mitosis_failure_isolates_and_preserves_aisa_claim(self):
        self.configure_aisa()
        self.configure_mitosis()

        def fake_http(url, body, headers, timeout):
            if url.startswith("https://aisa.test"):
                return 200, openai_style_response("evidence text"), {}
            raise urllib.error.URLError("mitosis unreachable")

        aisa_mitosis._http_json = fake_http
        result = aisa_mitosis.run_aisa_mitosis(ARTIFACT_REF, EFFECT, PRINCIPAL, TARGET)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["aisa"]["status"], "COMPLETED")
        self.assertEqual(result["mitosis"]["status"], "FAILED")
        self.assertIsNotNone(result["claim"])
        self.assertFalse(result["authority"])

    def test_sse_payload_from_mcp_is_parsed(self):
        parsed = aisa_mitosis._parse_maybe_sse(
            'event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"ok":true}}\n\n'
        )
        self.assertEqual(parsed["result"], {"ok": True})

    def test_invalid_artifact_ref_is_rejected_before_any_call(self):
        with self.assertRaises(RuntimeError):
            aisa_mitosis.run_aisa_mitosis("sha256:short", EFFECT, PRINCIPAL, TARGET)


if __name__ == "__main__":
    unittest.main()
