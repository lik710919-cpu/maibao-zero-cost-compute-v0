import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class PoolPlanTests(unittest.TestCase):
    def test_build_plan_combines_adaptive_chunking_and_provider_budgets(self):
        import build_pool_plan
        from capacity_scheduler import ProviderPolicy

        policies = [
            ProviderPolicy("github-actions-public", capacity=4, max_tasks_per_run=None, priority=0),
            ProviderPolicy("wandbox-public", capacity=1, max_tasks_per_run=1, priority=1),
        ]
        plan = build_pool_plan.build_plan(
            n=800000,
            target_items_per_chunk=100000,
            max_chunks=8,
            policies=policies,
            require_provider_count=2,
            compiler="cpython-3.13.8",
        )
        self.assertEqual(plan["chunks"], 8)
        self.assertEqual(len(plan["assignments"]), 8)
        self.assertEqual(plan["assignments"][4]["provider_id"], "wandbox-public")
        self.assertEqual(plan["assignment_counts"], {"github-actions-public": 7, "wandbox-public": 1})
        self.assertEqual(plan["provider_count"], 2)
        self.assertEqual(plan["local_formal_compute_percent"], 0)

    def test_build_plan_requires_requested_provider_count(self):
        import build_pool_plan
        from capacity_scheduler import ProviderPolicy

        with self.assertRaises(RuntimeError):
            build_pool_plan.build_plan(
                n=100,
                target_items_per_chunk=100,
                max_chunks=4,
                policies=[ProviderPolicy("github-actions-public", 4, None, 0)],
                require_provider_count=2,
                compiler="cpython-3.13.8",
            )


if __name__ == "__main__":
    unittest.main()
