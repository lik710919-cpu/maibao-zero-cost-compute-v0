import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class CapacitySchedulerTests(unittest.TestCase):
    def test_eight_shards_respect_capacity_and_wandbox_budget(self):
        import capacity_scheduler
        policies = [
            capacity_scheduler.ProviderPolicy("github-actions-public", capacity=4, max_tasks_per_run=None, priority=0),
            capacity_scheduler.ProviderPolicy("wandbox-public", capacity=1, max_tasks_per_run=1, priority=1),
        ]
        assignments = capacity_scheduler.assign_shards(8, policies)
        self.assertEqual([item["index"] for item in assignments], list(range(8)))
        counts = capacity_scheduler.assignment_counts(assignments)
        self.assertEqual(counts["wandbox-public"], 1)
        self.assertEqual(counts["github-actions-public"], 7)
        self.assertEqual(assignments[4]["provider_id"], "wandbox-public")

    def test_scheduler_is_deterministic(self):
        import capacity_scheduler
        policies = [
            capacity_scheduler.ProviderPolicy("github-actions-public", 4, None, 0),
            capacity_scheduler.ProviderPolicy("wandbox-public", 1, 1, 1),
        ]
        self.assertEqual(
            capacity_scheduler.assign_shards(8, policies),
            capacity_scheduler.assign_shards(8, policies),
        )

    def test_budget_is_never_exceeded(self):
        import capacity_scheduler
        policies = [
            capacity_scheduler.ProviderPolicy("a", 2, 2, 0),
            capacity_scheduler.ProviderPolicy("b", 1, 1, 1),
        ]
        assignments = capacity_scheduler.assign_shards(3, policies)
        counts = capacity_scheduler.assignment_counts(assignments)
        self.assertLessEqual(counts.get("a", 0), 2)
        self.assertLessEqual(counts.get("b", 0), 1)
        with self.assertRaises(RuntimeError):
            capacity_scheduler.assign_shards(4, policies)

    def test_invalid_policies_are_rejected(self):
        import capacity_scheduler
        with self.assertRaises(ValueError):
            capacity_scheduler.ProviderPolicy("", 1, 1, 0)
        with self.assertRaises(ValueError):
            capacity_scheduler.ProviderPolicy("a", 0, 1, 0)
        with self.assertRaises(ValueError):
            capacity_scheduler.assign_shards(0, [capacity_scheduler.ProviderPolicy("a", 1, None, 0)])


if __name__ == "__main__":
    unittest.main()
