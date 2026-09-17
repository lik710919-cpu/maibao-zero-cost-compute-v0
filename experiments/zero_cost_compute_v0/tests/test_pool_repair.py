import importlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compute_chunk import partition_range, sum_squares_formula


def make_primary(index: int, provider_id: str = "github-actions-public", n: int = 800_000, chunks: int = 8) -> dict:
    start, end = partition_range(n, chunks, index)
    return {
        "chunk_index": index,
        "chunks": chunks,
        "n": n,
        "range_start": start,
        "range_end": end,
        "partial_sum": sum_squares_formula(start, end),
        "attempt": "primary",
        "provider_id": provider_id,
        "scheduled_provider_id": provider_id,
        "provider_evidence": "run:123",
        "runner_environment": "github-hosted",
        "repo_visibility": "public",
        "local_compute_used": False,
    }


def make_plan() -> dict:
    return {
        "n": 800_000,
        "chunks": 8,
        "failure_index": 4,
        "assignments": [{"index": i, "provider_id": "github-actions-public"} for i in range(8)],
        "repair_provider_id": "wandbox-public",
        "repair_budgets": {"wandbox-public": 1},
        "compiler": "cpython-3.13.8",
    }


class PoolRepairTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("pool_repair")
        self.assertIsNotNone(spec, "pool_repair module must exist")
        if spec is None:
            return None
        return importlib.import_module("pool_repair")

    def test_only_missing_index_is_assigned_to_reserved_fallback(self):
        module = self._module()
        if module is None:
            return
        primaries = [make_primary(i) for i in range(8) if i != 4]
        repair = module.build_repair_plan(make_plan(), primaries)
        self.assertEqual(repair["repair_indexes"], [4])
        self.assertEqual(repair["repair_count"], 1)
        self.assertEqual(
            repair["repair_assignments"],
            [{"index": 4, "original_provider_id": "github-actions-public", "provider_id": "wandbox-public"}],
        )

    def test_provider_identity_mismatch_becomes_repair(self):
        module = self._module()
        if module is None:
            return
        primaries = [make_primary(i) for i in range(8)]
        primaries[3] = make_primary(3, provider_id="wandbox-public")
        repair = module.build_repair_plan(make_plan(), primaries)
        self.assertIn(3, repair["repair_indexes"])

    def test_duplicate_primary_becomes_repair(self):
        module = self._module()
        if module is None:
            return
        primaries = [make_primary(i) for i in range(8)] + [make_primary(2)]
        repair = module.build_repair_plan(make_plan(), primaries)
        self.assertIn(2, repair["repair_indexes"])

    def test_wrong_sum_becomes_repair(self):
        module = self._module()
        if module is None:
            return
        primaries = [make_primary(i) for i in range(8)]
        primaries[6]["partial_sum"] += 1
        repair = module.build_repair_plan(make_plan(), primaries)
        self.assertIn(6, repair["repair_indexes"])

    def test_rejects_more_repairs_than_reserved_budget(self):
        module = self._module()
        if module is None:
            return
        primaries = [make_primary(i) for i in range(8) if i not in {3, 4}]
        with self.assertRaises(RuntimeError):
            module.build_repair_plan(make_plan(), primaries)


if __name__ == "__main__":
    unittest.main()
