import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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

    def test_provider_snapshot_requires_real_evidence_and_free_tier(self):
        import provider_probe

        ready = provider_probe.huggingface_snapshot(
            "real:huggingface:run-1",
            healthy=True,
            free_tier_confirmed=True,
        )
        self.assertEqual(ready.provider_id, "huggingface-inference-providers")
        self.assertEqual(ready.status, "ready")
        self.assertTrue(ready.zero_cash_cost)

        unpaid = provider_probe.huggingface_snapshot(
            "real:huggingface:run-2",
            healthy=True,
            free_tier_confirmed=False,
        )
        self.assertNotEqual(unpaid.status, "ready")
        self.assertFalse(unpaid.zero_cash_cost)

    def test_shared_manifest_exposes_one_cross_repository_contract(self):
        manifest = json.loads((ROOT / "shared_capabilities.json").read_text(encoding="utf-8"))
        entries = {item["capability_id"]: item for item in manifest["capabilities"]}
        item = entries["huggingface-ai-inference"]
        self.assertEqual(item["scope"], "MAIBAO_SHARED")
        self.assertEqual(
            item["implementation_repository"],
            "lik710919-cpu/maibao-zero-cost-compute-v0",
        )
        self.assertEqual(item["provider_id"], "huggingface-inference-providers")
        self.assertFalse(item["generic_compute"])
        self.assertTrue(item["cross_repository_consumable"])

    def test_candidate_catalog_marks_huggingface_as_inference_only(self):
        candidates = json.loads((ROOT / "provider_candidates.json").read_text(encoding="utf-8"))
        entries = {item["provider_id"]: item for item in candidates}
        item = entries["huggingface-inference-providers"]
        self.assertEqual(item["compute_class"], "ai_inference")
        self.assertFalse(item["formal_pool_eligible"])
        self.assertEqual(item["lifecycle_state"], "adapter_ready")


    def test_browser_login_cache_supplies_token_when_explicit_token_is_absent(self):
        import huggingface_provider

        request = huggingface_provider.build_chat_completion_request(
            token=None,
            token_cache_getter=lambda: "hf_cached_secret",
            model="openai/gpt-oss-120b",
            prompt="return READY",
        )
        self.assertEqual(request.headers["Authorization"], "Bearer hf_cached_secret")
        self.assertNotIn("hf_cached_secret", json.dumps(request.safe_summary()))

    def test_explicit_token_wins_over_cached_token(self):
        import huggingface_provider

        request = huggingface_provider.build_chat_completion_request(
            token="hf_explicit_secret",
            token_cache_getter=lambda: "hf_cached_secret",
            model="openai/gpt-oss-120b",
            prompt="return READY",
        )
        self.assertEqual(request.headers["Authorization"], "Bearer hf_explicit_secret")

    def test_missing_browser_login_cache_fails_closed(self):
        import huggingface_provider

        with self.assertRaises(RuntimeError):
            huggingface_provider.build_chat_completion_request(
                token=None,
                token_cache_getter=lambda: None,
                model="openai/gpt-oss-120b",
                prompt="return READY",
            )

    def test_shared_manifest_prefers_official_browser_device_login(self):
        manifest = json.loads((ROOT / "shared_capabilities.json").read_text(encoding="utf-8"))
        item = manifest["capabilities"][0]
        self.assertEqual(item["auth_mode"], "huggingface_browser_device_oauth")
        self.assertEqual(item["token_source"], "huggingface_hub_standard_cache")
        self.assertTrue(item["manual_token_paste_not_required"])


    def test_live_activation_requires_free_tier_confirmation(self):
        import huggingface_activation

        with self.assertRaises(RuntimeError):
            huggingface_activation.activate(
                model="openai/gpt-oss-120b",
                prompt="Return exactly READY",
                expected_text="READY",
                confirm_free_tier=False,
                requester=lambda request: {
                    "id": "should-not-run",
                    "choices": [{"message": {"content": "READY"}}],
                },
                token_cache_getter=lambda: "hf_cached_secret",
            )

    def test_live_activation_reuses_browser_cache_and_returns_ready(self):
        import huggingface_activation

        evidence = huggingface_activation.activate(
            model="openai/gpt-oss-120b",
            prompt="Return exactly READY",
            expected_text="READY",
            confirm_free_tier=True,
            requester=lambda request: {
                "id": "chatcmpl-live-proof",
                "choices": [{"message": {"content": "READY"}}],
            },
            token_cache_getter=lambda: "hf_cached_secret",
        )
        self.assertEqual(evidence["activation_state"], "READY")
        self.assertEqual(evidence["auth_mode"], "huggingface_browser_device_oauth")
        self.assertEqual(evidence["token_source"], "huggingface_hub_standard_cache")
        self.assertFalse(evidence["manual_token_paste_used"])
        self.assertTrue(evidence["free_tier_guard"])


if __name__ == "__main__":
    unittest.main()
