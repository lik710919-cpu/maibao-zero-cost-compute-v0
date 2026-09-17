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


if __name__ == "__main__":
    unittest.main()
