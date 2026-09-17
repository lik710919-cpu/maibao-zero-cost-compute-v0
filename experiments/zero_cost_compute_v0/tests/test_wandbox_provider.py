import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class WandboxProviderTests(unittest.TestCase):
    def test_wandbox_response_requires_matching_challenge(self):
        import wandbox_chunk
        raw = {
            "status": "0",
            "program_output": json.dumps({"challenge": "abc", "partial_sum": 330}) + "\n",
        }
        parsed = wandbox_chunk.parse_wandbox_response(raw, "abc")
        self.assertEqual(parsed["partial_sum"], 330)
        with self.assertRaises(RuntimeError):
            wandbox_chunk.parse_wandbox_response(raw, "wrong")

    def test_provider_aware_aggregation_accepts_github_and_wandbox(self):
        import aggregate_results
        github = {
            "chunk_index": 0, "chunks": 2, "n": 10,
            "range_start": 1, "range_end": 5, "partial_sum": 55,
            "attempt": "primary", "provider_id": "github-actions-public",
            "runner_environment": "github-hosted", "repo_visibility": "public",
            "local_compute_used": False, "runner_name": "gh-1", "hostname": "gh",
        }
        wandbox = {
            "chunk_index": 1, "chunks": 2, "n": 10,
            "range_start": 6, "range_end": 10, "partial_sum": 330,
            "attempt": "primary", "provider_id": "wandbox-public",
            "runner_environment": "wandbox-public-api", "repo_visibility": "public",
            "local_compute_used": False, "runner_name": "wandbox", "hostname": "wandbox.org",
            "provider_evidence": "real:wandbox:test",
        }
        with tempfile.TemporaryDirectory() as td:
            p0 = Path(td) / "result-0.json"
            p1 = Path(td) / "result-1.json"
            p0.write_text(json.dumps(github), encoding="utf-8")
            p1.write_text(json.dumps(wandbox), encoding="utf-8")
            evidence = aggregate_results.verify_results([p0, p1], 10, 2)
        self.assertEqual(evidence["execution_provider_count"], 2)
        self.assertEqual(
            evidence["execution_provider_ids"],
            ["github-actions-public", "wandbox-public"],
        )
        self.assertTrue(evidence["cross_provider_closed"])
        self.assertEqual(evidence["combined_sum"], 385)

    def test_wandbox_snapshot_needs_successful_real_evidence(self):
        import provider_probe
        ready = provider_probe.wandbox_snapshot("real:wandbox:run-1", "0", "cpython-3.13.8")
        self.assertTrue(ready.authorized)
        self.assertTrue(ready.healthy)
        self.assertTrue(ready.zero_cash_cost)
        self.assertEqual(ready.status, "ready")
        failed = provider_probe.wandbox_snapshot("none", "1", "cpython-3.13.8")
        self.assertNotEqual(failed.status, "ready")


if __name__ == "__main__":
    unittest.main()
