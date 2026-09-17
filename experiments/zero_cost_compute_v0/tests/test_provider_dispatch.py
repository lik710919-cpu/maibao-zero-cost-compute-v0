import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ProviderDispatchTests(unittest.TestCase):
    def test_primary_success_does_not_call_fallback(self):
        import provider_dispatch
        calls = []

        def execute(provider_id):
            calls.append(provider_id)
            return {"provider_id": provider_id, "partial_sum": 1}

        result = provider_dispatch.dispatch_with_failover(
            {"primary": "a", "fallbacks": ["b"]}, execute
        )
        self.assertEqual(calls, ["a"])
        self.assertEqual(result["provider_id"], "a")
        self.assertEqual(result["dispatch_attempts"], [{"provider_id": "a", "status": "success"}])

    def test_primary_failure_automatically_uses_fallback(self):
        import provider_dispatch
        calls = []

        def execute(provider_id):
            calls.append(provider_id)
            if provider_id == "a":
                raise RuntimeError("controlled failure")
            return {"provider_id": provider_id, "partial_sum": 2}

        result = provider_dispatch.dispatch_with_failover(
            {"primary": "a", "fallbacks": ["b"]}, execute
        )
        self.assertEqual(calls, ["a", "b"])
        self.assertEqual(result["provider_id"], "b")
        self.assertEqual(
            result["dispatch_attempts"],
            [
                {"provider_id": "a", "status": "failed", "error": "controlled failure"},
                {"provider_id": "b", "status": "success"},
            ],
        )

    def test_exhausted_route_fails_closed(self):
        import provider_dispatch

        def execute(provider_id):
            raise RuntimeError(f"{provider_id} unavailable")

        with self.assertRaises(RuntimeError) as ctx:
            provider_dispatch.dispatch_with_failover(
                {"primary": "a", "fallbacks": ["b"]}, execute
            )
        self.assertIn("all routed providers failed", str(ctx.exception))

    def test_invalid_or_duplicate_route_rejected(self):
        import provider_dispatch
        with self.assertRaises(ValueError):
            provider_dispatch.dispatch_with_failover({"primary": "a", "fallbacks": ["a"]}, lambda _: {})
        with self.assertRaises(ValueError):
            provider_dispatch.dispatch_with_failover({"primary": "", "fallbacks": []}, lambda _: {})


if __name__ == "__main__":
    unittest.main()
