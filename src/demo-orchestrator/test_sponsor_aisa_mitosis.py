import importlib.util
import os
import pathlib
import unittest

MODULE_DIR = pathlib.Path(__file__).parent
MODULE_PATH = MODULE_DIR / "sponsor_aisa_mitosis.py"
SPEC = importlib.util.spec_from_file_location("sponsor_aisa_mitosis", MODULE_PATH)
sponsor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sponsor)


class AIsaMitosisSponsorTests(unittest.TestCase):
    def setUp(self):
        self.saved_env = dict(os.environ)
        self.original_call_aisa = sponsor._call_aisa
        self.original_remember = sponsor._remember_with_mitosis

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved_env)
        sponsor._call_aisa = self.original_call_aisa
        sponsor._remember_with_mitosis = self.original_remember

    def test_missing_credentials_is_truthful_pending(self):
        os.environ.pop("AISA_API_KEY", None)
        os.environ.pop("MITOSIS_OFFICE_ID", None)
        os.environ.pop("MI_OFFICE_ID", None)
        result = sponsor.run_aisa_mitosis_evidence("test query")
        self.assertEqual(result["status"], "PENDING")
        self.assertFalse(result["live"])
        self.assertFalse(result["authority"])

    def test_real_path_envelope_remains_non_authoritative(self):
        os.environ["AISA_API_KEY"] = "test-key"
        os.environ["MITOSIS_OFFICE_ID"] = "office-test"
        sponsor._call_aisa = lambda key, query: {
            "results": [{"title": "example", "url": "https://example.test"}]
        }
        sponsor._remember_with_mitosis = lambda office, text: {
            "status": "ok",
            "universal_id": "agent_memory:oasse-hackathon:test",
        }
        result = sponsor.run_aisa_mitosis_evidence("test query")
        self.assertEqual(result["status"], "LIVE")
        self.assertTrue(result["live"])
        self.assertFalse(result["authority"])
        self.assertTrue(result["gatekeeper_authority_required_for_effects"])
        self.assertNotIn("permit", result)
        self.assertNotIn("token", result)
        self.assertNotIn("gatekeeper_verdict", result)

    def test_mitosis_failure_never_promotes_aisa_only_result_to_live(self):
        os.environ["AISA_API_KEY"] = "test-key"
        os.environ["MITOSIS_OFFICE_ID"] = "office-test"
        sponsor._call_aisa = lambda key, query: {"results": [{"title": "example"}]}

        def fail_remember(office, text):
            raise RuntimeError("write unavailable")

        sponsor._remember_with_mitosis = fail_remember
        result = sponsor.run_aisa_mitosis_evidence("test query")
        self.assertEqual(result["status"], "PENDING")
        self.assertFalse(result["live"])
        self.assertFalse(result["authority"])
        self.assertTrue(result["aisa_live"])
        self.assertFalse(result["mitosis_live"])


class MiOutputParsingTests(unittest.TestCase):
    def test_json_stdout_is_parsed(self):
        parsed = sponsor._parse_mi_output(
            '{"status":"ok","embedded":true,"universal_id":"agent:memories:31c72bd7c48e54f597d136e3"}'
        )
        self.assertEqual(parsed["status"], "ok")
        self.assertTrue(parsed["embedded"])
        self.assertEqual(
            parsed["universal_id"], "agent:memories:31c72bd7c48e54f597d136e3"
        )

    def test_key_value_stdout_is_parsed(self):
        parsed = sponsor._parse_mi_output(
            "status: ok\nembedded: true\nuniversal_id: agent:memories:31c72bd7c48e54f597d136e3\n"
        )
        self.assertEqual(parsed["status"], "ok")
        self.assertIs(parsed["embedded"], True)
        self.assertEqual(
            parsed["universal_id"], "agent:memories:31c72bd7c48e54f597d136e3"
        )

    def test_empty_stdout_still_reports_ok(self):
        self.assertEqual(sponsor._parse_mi_output(""), {"status": "ok"})

    def test_mi_command_has_no_json_flag(self):
        observed = {}

        class FakeCompleted:
            returncode = 0
            stdout = "status: ok\nembedded: true\nuniversal_id: agent:memories:test\n"
            stderr = ""

        original_which = sponsor.shutil.which
        original_run = sponsor.subprocess.run
        sponsor.shutil.which = lambda name: "/usr/local/bin/mi" if name == "mi" else None

        def fake_run(command, **kwargs):
            observed["command"] = command
            return FakeCompleted()

        sponsor.subprocess.run = fake_run
        try:
            payload = sponsor._remember_with_mitosis("office-test", "evidence text")
        finally:
            sponsor.shutil.which = original_which
            sponsor.subprocess.run = original_run

        self.assertNotIn("--json", observed["command"])
        self.assertIn("--office", observed["command"])
        self.assertEqual(payload["universal_id"], "agent:memories:test")
        self.assertIs(payload["embedded"], True)


if __name__ == "__main__":
    unittest.main()
