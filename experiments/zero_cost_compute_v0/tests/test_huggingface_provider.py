import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class HuggingFaceProviderTests(unittest.TestCase):
    def test_build_request_targets_router_and_redacts_token(self):
        import huggingface_provider

        request = huggingface_provider.build_chat_completion_request(
            token="hf_secret",
            model="openai/gpt-oss-120b",
            prompt="return READY",
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.url,
            "https://router.huggingface.co/v1/chat/completions",
        )
        self.assertEqual(request.body["model"], "openai/gpt-oss-120b")
        self.assertEqual(request.body["messages"][0]["content"], "return READY")
        self.assertEqual(request.headers["Authorization"], "Bearer hf_secret")
        summary = request.safe_summary()
        self.assertNotIn("hf_secret", json.dumps(summary))
        self.assertTrue(summary["token_present"])

    def test_parse_response_requires_text_output(self):
        import huggingface_provider

        parsed = huggingface_provider.parse_chat_completion_response(
            {
                "id": "chatcmpl-test",
                "choices": [
                    {"message": {"role": "assistant", "content": "READY"}}
                ],
            }
        )
        self.assertEqual(parsed["text"], "READY")
        with self.assertRaises(ValueError):
            huggingface_provider.parse_chat_completion_response({"choices": []})

    def test_verified_probe_is_shareable_but_not_generic_compute(self):
        import huggingface_provider

        evidence = huggingface_provider.build_verified_evidence(
            response={"id": "chatcmpl-test", "choices": [{"message": {"content": "READY"}}]},
            expected_text="READY",
            model="openai/gpt-oss-120b",
            free_tier_confirmed=True,
        )
        self.assertTrue(evidence["verified"])
        self.assertFalse(evidence["local_compute_used"])
        self.assertEqual(evidence["provider_id"], "huggingface-inference-providers")
        self.assertEqual(evidence["capability_scope"], "MAIBAO_SHARED")
        self.assertEqual(evidence["capability_kind"], "ai_inference")
        self.assertFalse(evidence["generic_compute"])


if __name__ == "__main__":
    unittest.main()
