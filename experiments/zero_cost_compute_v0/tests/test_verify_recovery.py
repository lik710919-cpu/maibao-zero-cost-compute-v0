import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compute_chunk import partition_range, sum_squares_formula

RUN_ID = "999"
N = 800_000
CHUNKS = 8


def make_result(index: int, provider_id: str, attempt: str, run_id: str = RUN_ID) -> dict:
    start, end = partition_range(N, CHUNKS, index)
    if provider_id == "github-actions-public":
        environment = "github-hosted"
        evidence = f"run:{run_id}"
        hostname = "github-host"
    else:
        environment = "wandbox-public-api"
        evidence = f"real:wandbox:{run_id}:proof"
        hostname = "wandbox.org"
    return {
        "chunk_index": index,
        "chunks": CHUNKS,
        "n": N,
        "range_start": start,
        "range_end": end,
        "partial_sum": sum_squares_formula(start, end),
        "attempt": attempt,
        "provider_id": provider_id,
        "scheduled_provider_id": provider_id,
        "original_provider_id": "github-actions-public" if attempt == "repair" else None,
        "provider_evidence": evidence,
        "runner_environment": environment,
        "repo_visibility": "public",
        "hostname": hostname,
        "runner_name": provider_id,
        "local_compute_used": False,
    }


def make_plan() -> dict:
    return {
        "n": N,
        "chunks": CHUNKS,
        "failure_index": 4,
        "assignments": [{"index": i, "provider_id": "github-actions-public"} for i in range(CHUNKS)],
        "repair_provider_id": "wandbox-public",
        "repair_budgets": {"wandbox-public": 1},
    }


def make_repair_plan() -> dict:
    return {
        "repair_indexes": [4],
        "repair_count": 1,
        "repair_assignments": [
            {"index": 4, "original_provider_id": "github-actions-public", "provider_id": "wandbox-public"}
        ],
    }


def make_results() -> list[dict]:
    values = [make_result(i, "github-actions-public", "primary") for i in range(CHUNKS) if i != 4]
    values.append(make_result(4, "wandbox-public", "repair"))
    return values


def make_aggregate() -> dict:
    total = sum_squares_formula(1, N)
    return {
        "status": "PASS",
        "worker_count": 8,
        "primary_valid_count": 7,
        "repaired_result_count": 1,
        "recovered_indexes": [4],
        "execution_provider_ids": ["github-actions-public", "wandbox-public"],
        "execution_provider_count": 2,
        "cross_provider_closed": True,
        "local_formal_compute_percent": 0,
        "combined_sum": total,
        "expected_sum": total,
    }


class RecoveryVerificationTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("verify_recovery")
        self.assertIsNotNone(spec, "verify_recovery module must exist")
        if spec is None:
            return None
        return importlib.import_module("verify_recovery")

    def test_accepts_exactly_seven_primary_and_one_cross_provider_repair(self):
        module = self._module()
        if module is None:
            return
        evidence = module.verify_recovery(make_plan(), make_repair_plan(), make_results(), make_aggregate(), RUN_ID)
        self.assertEqual(evidence["status"], "PASS")
        self.assertEqual(evidence["primary_valid_count"], 7)
        self.assertEqual(evidence["repaired_result_count"], 1)
        self.assertEqual(evidence["recovered_indexes"], [4])
        self.assertEqual(evidence["primary_provider_counts"], {"github-actions-public": 7})
        self.assertEqual(evidence["repair_provider_counts"], {"wandbox-public": 1})
        self.assertEqual(evidence["local_formal_compute_percent"], 0)

    def test_rejects_duplicate_repair(self):
        module = self._module()
        if module is None:
            return
        results = make_results() + [make_result(4, "wandbox-public", "repair")]
        with self.assertRaises(RuntimeError):
            module.verify_recovery(make_plan(), make_repair_plan(), results, make_aggregate(), RUN_ID)

    def test_rejects_wrong_recovery_index(self):
        module = self._module()
        if module is None:
            return
        repair_plan = make_repair_plan()
        repair_plan["repair_indexes"] = [3]
        repair_plan["repair_assignments"][0]["index"] = 3
        with self.assertRaises(RuntimeError):
            module.verify_recovery(make_plan(), repair_plan, make_results(), make_aggregate(), RUN_ID)

    def test_rejects_same_provider_repair(self):
        module = self._module()
        if module is None:
            return
        results = [make_result(i, "github-actions-public", "primary") for i in range(CHUNKS) if i != 4]
        results.append(make_result(4, "github-actions-public", "repair"))
        with self.assertRaises(RuntimeError):
            module.verify_recovery(make_plan(), make_repair_plan(), results, make_aggregate(), RUN_ID)

    def test_rejects_stale_provider_evidence(self):
        module = self._module()
        if module is None:
            return
        results = make_results()
        results[-1] = make_result(4, "wandbox-public", "repair", run_id="old-run")
        with self.assertRaises(RuntimeError):
            module.verify_recovery(make_plan(), make_repair_plan(), results, make_aggregate(), RUN_ID)


if __name__ == "__main__":
    unittest.main()
