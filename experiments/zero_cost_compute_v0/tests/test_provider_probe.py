import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ProviderProbeTests(unittest.TestCase):
    def test_public_github_hosted_run_becomes_real_zero_cost_provider(self):
        import provider_probe
        snapshot = provider_probe.github_hosted_snapshot(
            run_id="35191663499",
            runner_environment="github-hosted",
            repository_visibility="public",
            queue_seconds=4.0,
            capacity=4,
        )
        self.assertTrue(snapshot.authorized)
        self.assertTrue(snapshot.healthy)
        self.assertTrue(snapshot.zero_cash_cost)
        self.assertEqual(snapshot.evidence, "run:35191663499")
        self.assertEqual(snapshot.status, "ready")

    def test_non_public_or_non_hosted_github_run_fails_closed(self):
        import provider_probe
        private = provider_probe.github_hosted_snapshot("1", "github-hosted", "private", 0, 4)
        self.assertFalse(private.zero_cash_cost)
        self.assertNotEqual(private.status, "ready")
        self_hosted = provider_probe.github_hosted_snapshot("2", "self-hosted", "public", 0, 4)
        self.assertFalse(self_hosted.healthy)
        self.assertNotEqual(self_hosted.status, "ready")

    def test_current_catalog_does_not_promote_unproven_candidates(self):
        import provider_probe
        catalog = provider_probe.current_catalog(
            run_id="35191663499",
            runner_environment="github-hosted",
            repository_visibility="public",
            queue_seconds=4.0,
            capacity=4,
        )
        self.assertEqual(catalog["live_provider_count"], 1)
        self.assertEqual(catalog["live_provider_ids"], ["github-actions-public"])
        self.assertEqual(catalog["execution_provider_ids"], ["github-actions-public"])
        self.assertFalse(catalog["cross_provider_closed"])
        self.assertEqual(catalog["route"]["primary"], "github-actions-public")
        self.assertEqual(catalog["candidate_provider_ids"], ["netlify-free", "vercel-free"])
        candidates = [p for p in catalog["providers"] if p["provider_id"] != "github-actions-public"]
        self.assertTrue(all(not p["authorized"] for p in candidates))
        self.assertTrue(all(not p["zero_cash_cost"] for p in candidates))


if __name__ == "__main__":
    unittest.main()
