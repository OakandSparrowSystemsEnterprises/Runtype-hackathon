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


if __name__ == "__main__":
    unittest.main()
