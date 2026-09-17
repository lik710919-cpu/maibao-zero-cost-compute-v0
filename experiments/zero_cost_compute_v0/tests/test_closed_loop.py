import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aggregate_results
from compute_chunk import partition_range, sum_squares_formula


def make_result(index: int, chunks: int, n: int, attempt: str = "primary") -> dict:
    start, end = partition_range(n, chunks, index)
    return {
        "chunk_index": index,
        "chunks": chunks,
        "n": n,
        "range_start": start,
        "range_end": end,
        "partial_sum": sum_squares_formula(start, end),
        "runner_name": f"runner-{index}-{attempt}",
        "runner_environment": "github-hosted",
        "repo_visibility": "public",
        "local_compute_used": False,
        "attempt": attempt,
        "hostname": f"host-{index}-{attempt}",
        "duration_seconds": 0.01,
    }


class ClosedLoopTests(unittest.TestCase):
    def test_automatic_shard_count(self):
        spec = importlib.util.find_spec("plan_work")
        self.assertIsNotNone(spec, "plan_work module must exist")
        if spec is None:
            return
        module = importlib.import_module("plan_work")
        self.assertEqual(module.choose_chunk_count(40_000_000, 5_000_000, 16), 8)
        self.assertEqual(module.choose_chunk_count(1, 5_000_000, 16), 1)
        self.assertEqual(module.choose_chunk_count(100_000_000, 1_000_000, 16), 16)

    def test_repair_planner_returns_only_missing_index(self):
        spec = importlib.util.find_spec("plan_repairs")
        self.assertIsNotNone(spec, "plan_repairs module must exist")
        if spec is None:
            return
        module = importlib.import_module("plan_repairs")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in (0, 1, 3):
                (root / f"result-{index}.json").write_text(
                    json.dumps(make_result(index, 4, 20)), encoding="utf-8"
                )
            self.assertEqual(module.find_repair_indexes(root, 20, 4), [2])

    def test_dynamic_aggregation_accepts_repaired_shard(self):
        verify = getattr(aggregate_results, "verify_results", None)
        self.assertIsNotNone(verify, "aggregate_results.verify_results must exist")
        if verify is None:
            return
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for index in (0, 1, 3):
                path = root / f"primary-{index}.json"
                path.write_text(json.dumps(make_result(index, 4, 20)), encoding="utf-8")
                paths.append(path)
            repair = root / "repair-2.json"
            repair.write_text(json.dumps(make_result(2, 4, 20, "repair")), encoding="utf-8")
            paths.append(repair)
            evidence = verify(paths, expected_n=20, expected_chunks=4)
            self.assertEqual(evidence["status"], "PASS")
            self.assertEqual(evidence["automatic_chunk_count"], 4)
            self.assertEqual(evidence["repaired_result_count"], 1)
            self.assertEqual(evidence["recovered_indexes"], [2])
            self.assertEqual(evidence["combined_sum"], evidence["expected_sum"])


if __name__ == "__main__":
    unittest.main()
