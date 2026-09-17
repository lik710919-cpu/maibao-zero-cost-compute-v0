import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AssignedChunkTests(unittest.TestCase):
    def test_github_assignment_calls_only_github_executor(self):
        import assigned_chunk
        calls = []
        result = assigned_chunk.execute_assigned_provider(
            "github-actions-public",
            lambda: calls.append("github") or {"provider_id": "github-actions-public"},
            lambda: calls.append("wandbox") or {"provider_id": "wandbox-public"},
        )
        self.assertEqual(calls, ["github"])
        self.assertEqual(result["scheduled_provider_id"], "github-actions-public")

    def test_wandbox_assignment_calls_only_wandbox_executor(self):
        import assigned_chunk
        calls = []
        result = assigned_chunk.execute_assigned_provider(
            "wandbox-public",
            lambda: calls.append("github") or {"provider_id": "github-actions-public"},
            lambda: calls.append("wandbox") or {"provider_id": "wandbox-public"},
        )
        self.assertEqual(calls, ["wandbox"])
        self.assertEqual(result["scheduled_provider_id"], "wandbox-public")

    def test_provider_identity_mismatch_fails_closed(self):
        import assigned_chunk
        with self.assertRaises(RuntimeError):
            assigned_chunk.execute_assigned_provider(
                "wandbox-public",
                lambda: {"provider_id": "github-actions-public"},
                lambda: {"provider_id": "github-actions-public"},
            )

    def test_unknown_provider_fails_closed(self):
        import assigned_chunk
        with self.assertRaises(RuntimeError):
            assigned_chunk.execute_assigned_provider("unknown", lambda: {}, lambda: {})


if __name__ == "__main__":
    unittest.main()
