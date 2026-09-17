import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from provider_model import ProviderSnapshot


class RecoveryPlanTests(unittest.TestCase):
    def test_reserves_wandbox_and_assigns_all_primary_shards_to_github(self):
        spec = importlib.util.find_spec("build_recovery_plan")
        self.assertIsNotNone(spec, "build_recovery_plan module must exist")
        if spec is None:
            return
        module = importlib.import_module("build_recovery_plan")
        providers = [
            ProviderSnapshot("github-actions-public", True, True, True, 0.0, 4, "run:1", "ready"),
            ProviderSnapshot("wandbox-public", True, True, True, 0.0, 1, "real:wandbox:1:proof", "ready"),
        ]
        plan = module.build_recovery_plan(800_000, 100_000, 8, "cpython-3.13.8", providers)
        self.assertEqual(plan["chunks"], 8)
        self.assertEqual(plan["failure_index"], 4)
        self.assertEqual(len(plan["assignments"]), 8)
        self.assertEqual({item["provider_id"] for item in plan["assignments"]}, {"github-actions-public"})
        self.assertEqual(plan["repair_provider_id"], "wandbox-public")
        self.assertEqual(plan["repair_budgets"], {"wandbox-public": 1})
        self.assertEqual(plan["local_formal_compute_percent"], 0)

    def test_rejects_unavailable_or_nonzero_cost_fallback(self):
        spec = importlib.util.find_spec("build_recovery_plan")
        self.assertIsNotNone(spec, "build_recovery_plan module must exist")
        if spec is None:
            return
        module = importlib.import_module("build_recovery_plan")
        providers = [
            ProviderSnapshot("github-actions-public", True, True, True, 0.0, 4, "run:1", "ready"),
            ProviderSnapshot("wandbox-public", True, True, False, 0.0, 1, "real:wandbox:1:proof", "ready"),
        ]
        with self.assertRaises(RuntimeError):
            module.build_recovery_plan(800_000, 100_000, 8, "cpython-3.13.8", providers)


if __name__ == "__main__":
    unittest.main()
