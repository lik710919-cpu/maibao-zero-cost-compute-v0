import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ProviderRoutingTests(unittest.TestCase):
    def _modules(self):
        import provider_model
        import provider_router
        return provider_model, provider_router

    def test_rejects_unauthorized_unhealthy_nonzero_cost_and_unproven(self):
        model, router = self._modules()
        P = model.ProviderSnapshot
        providers = [
            P("good", True, True, True, 9, 2, "run:real", "ready"),
            P("unauthorized", False, True, True, 1, 99, "none", "authorization_required"),
            P("unhealthy", True, False, True, 1, 99, "run:real", "unhealthy"),
            P("unknown-cost", True, True, False, 1, 99, "run:real", "paid_or_unknown"),
            P("synthetic-only", True, True, True, 0, 99, "synthetic", "ready"),
        ]
        self.assertEqual([p.provider_id for p in router.eligible_providers(providers)], ["good"])

    def test_prefers_lower_queue_then_capacity(self):
        model, router = self._modules()
        P = model.ProviderSnapshot
        providers = [
            P("slow", True, True, True, 30, 100, "run:slow", "ready"),
            P("fast-small", True, True, True, 5, 2, "run:small", "ready"),
            P("fast-big", True, True, True, 5, 8, "run:big", "ready"),
        ]
        route = router.route_provider(providers)
        self.assertEqual(route["primary"], "fast-big")
        self.assertEqual(route["fallbacks"], ["fast-small", "slow"])

    def test_fails_closed_when_none_eligible(self):
        model, router = self._modules()
        P = model.ProviderSnapshot
        providers = [P("candidate", False, True, True, 0, 10, "none", "authorization_required")]
        with self.assertRaises(RuntimeError):
            router.route_provider(providers)


if __name__ == "__main__":
    unittest.main()
