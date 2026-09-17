import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class VerifyPoolTests(unittest.TestCase):
    def sample_plan(self):
        return {
            "chunks": 2,
            "assignments": [
                {"index": 0, "provider_id": "github-actions-public"},
                {"index": 1, "provider_id": "wandbox-public"},
            ],
            "assignment_counts": {"github-actions-public": 1, "wandbox-public": 1},
            "provider_count": 2,
            "local_formal_compute_percent": 0,
        }

    def test_matching_plan_and_results_pass(self):
        import verify_pool
        results = [
            {"chunk_index": 0, "provider_id": "github-actions-public", "scheduled_provider_id": "github-actions-public", "local_compute_used": False},
            {"chunk_index": 1, "provider_id": "wandbox-public", "scheduled_provider_id": "wandbox-public", "local_compute_used": False},
        ]
        report = verify_pool.verify_pool(self.sample_plan(), results)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["worker_count"], 2)
        self.assertEqual(report["assignment_counts"], {"github-actions-public": 1, "wandbox-public": 1})
        self.assertEqual(report["local_formal_compute_percent"], 0)

    def test_provider_identity_mismatch_fails_closed(self):
        import verify_pool
        results = [
            {"chunk_index": 0, "provider_id": "wandbox-public", "scheduled_provider_id": "github-actions-public", "local_compute_used": False},
            {"chunk_index": 1, "provider_id": "wandbox-public", "scheduled_provider_id": "wandbox-public", "local_compute_used": False},
        ]
        with self.assertRaises(RuntimeError):
            verify_pool.verify_pool(self.sample_plan(), results)

    def test_missing_or_duplicate_result_fails_closed(self):
        import verify_pool
        duplicate = [
            {"chunk_index": 0, "provider_id": "github-actions-public", "scheduled_provider_id": "github-actions-public", "local_compute_used": False},
            {"chunk_index": 0, "provider_id": "github-actions-public", "scheduled_provider_id": "github-actions-public", "local_compute_used": False},
        ]
        with self.assertRaises(RuntimeError):
            verify_pool.verify_pool(self.sample_plan(), duplicate)


if __name__ == "__main__":
    unittest.main()
