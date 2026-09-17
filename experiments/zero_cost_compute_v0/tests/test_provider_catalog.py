import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from provider_model import ProviderSnapshot


class ProviderCatalogTests(unittest.TestCase):
    def test_only_real_ready_providers_count_as_live(self):
        import provider_catalog
        providers = [
            ProviderSnapshot("github-hosted", True, True, True, 4, 4, "run:123", "ready"),
            ProviderSnapshot("candidate-b", False, True, True, 0, 100, "none", "authorization_required"),
            ProviderSnapshot("candidate-c", True, False, True, 0, 100, "probe-failed", "unhealthy"),
        ]
        evidence = provider_catalog.build_catalog(providers)
        self.assertEqual(evidence["live_provider_count"], 1)
        self.assertEqual(evidence["live_provider_ids"], ["github-hosted"])
        self.assertEqual(evidence["local_formal_compute_percent"], 0)
        self.assertEqual(evidence["route"]["primary"], "github-hosted")
        self.assertFalse(evidence["cross_provider_closed"])

    def test_cross_provider_closure_requires_two_distinct_ready_providers(self):
        import provider_catalog
        providers = [
            ProviderSnapshot("a", True, True, True, 2, 2, "real-a", "ready"),
            ProviderSnapshot("b", True, True, True, 3, 2, "real-b", "ready"),
        ]
        evidence = provider_catalog.build_catalog(providers)
        self.assertEqual(evidence["live_provider_count"], 2)
        self.assertTrue(evidence["cross_provider_closed"])
        self.assertEqual(evidence["route"]["primary"], "a")
        self.assertEqual(evidence["route"]["fallbacks"], ["b"])


if __name__ == "__main__":
    unittest.main()
