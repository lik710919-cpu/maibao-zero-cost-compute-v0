#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path

from aggregate_results import is_valid_result, provider_id_for


def _evidence_matches_run(item: dict, expected_run_id: str) -> bool:
    provider_id = provider_id_for(item)
    evidence = str(item.get("provider_evidence", ""))
    if provider_id == "github-actions-public":
        return evidence == f"run:{expected_run_id}"
    if provider_id == "wandbox-public":
        return evidence.startswith(f"real:wandbox:{expected_run_id}:")
    return False


def verify_recovery(
    plan: dict,
    repair_plan: dict,
    results: list[dict],
    aggregate_evidence: dict,
    expected_run_id: str,
) -> dict:
    n = int(plan["n"])
    chunks = int(plan["chunks"])
    failure_index = int(plan["failure_index"])
    assignments = {int(item["index"]): str(item["provider_id"]) for item in plan["assignments"]}
    if set(assignments) != set(range(chunks)):
        raise RuntimeError("primary plan does not cover all shards exactly once")

    repair_indexes = list(repair_plan.get("repair_indexes", []))
    repair_assignments = list(repair_plan.get("repair_assignments", []))
    if repair_indexes != [failure_index] or int(repair_plan.get("repair_count", -1)) != 1:
        raise RuntimeError("recovery must repair exactly the injected failure index")
    if len(repair_assignments) != 1 or int(repair_assignments[0].get("index", -1)) != failure_index:
        raise RuntimeError("repair assignment does not match injected failure index")

    by_index: dict[int, list[dict]] = {index: [] for index in range(chunks)}
    for item in results:
        index = item.get("chunk_index")
        if isinstance(index, int) and index in by_index:
            by_index[index].append(item)

    primary_counts: Counter[str] = Counter()
    repair_counts: Counter[str] = Counter()
    recovered_indexes: list[int] = []
    chosen: list[dict] = []

    for index in range(chunks):
        valid = [item for item in by_index[index] if is_valid_result(item, n, chunks, index)]
        if len(valid) != 1:
            raise RuntimeError(f"shard {index} must have exactly one valid final result")
        item = valid[0]
        if not _evidence_matches_run(item, expected_run_id):
            raise RuntimeError(f"shard {index} does not have current-run provider evidence")

        provider_id = provider_id_for(item)
        attempt = item.get("attempt", "primary")
        if index == failure_index:
            assignment = repair_assignments[0]
            original_provider_id = assignments[index]
            expected_repair_provider = str(assignment["provider_id"])
            if attempt != "repair":
                raise RuntimeError("failed shard must be represented by a repair result")
            if provider_id != expected_repair_provider:
                raise RuntimeError("repair result provider does not match repair plan")
            if provider_id == original_provider_id:
                raise RuntimeError("repair result reused the failed primary provider")
            if item.get("original_provider_id") != original_provider_id:
                raise RuntimeError("repair result lost original provider provenance")
            if item.get("scheduled_provider_id") != expected_repair_provider:
                raise RuntimeError("repair scheduled provider identity mismatch")
            repair_counts[provider_id] += 1
            recovered_indexes.append(index)
        else:
            expected_provider = assignments[index]
            if attempt != "primary":
                raise RuntimeError(f"healthy shard {index} was unnecessarily repaired")
            if provider_id != expected_provider or item.get("scheduled_provider_id") != expected_provider:
                raise RuntimeError(f"primary shard {index} provider identity mismatch")
            primary_counts[provider_id] += 1
        chosen.append(item)

    if len(results) != chunks:
        raise RuntimeError("final result set contains duplicate or extraneous shard results")

    expected_total = aggregate_evidence.get("expected_sum")
    if aggregate_evidence.get("status") != "PASS":
        raise RuntimeError("aggregate verification did not pass")
    if aggregate_evidence.get("combined_sum") != expected_total:
        raise RuntimeError("aggregate combined sum does not equal expected sum")
    if aggregate_evidence.get("worker_count") != chunks:
        raise RuntimeError("aggregate worker count mismatch")
    if aggregate_evidence.get("primary_valid_count") != chunks - 1:
        raise RuntimeError("aggregate primary count mismatch")
    if aggregate_evidence.get("repaired_result_count") != 1:
        raise RuntimeError("aggregate repair count mismatch")
    if aggregate_evidence.get("recovered_indexes") != [failure_index]:
        raise RuntimeError("aggregate recovered index mismatch")
    if aggregate_evidence.get("cross_provider_closed") is not True:
        raise RuntimeError("aggregate did not prove cross-provider closure")
    if aggregate_evidence.get("local_formal_compute_percent") != 0:
        raise RuntimeError("local formal compute was used")

    return {
        "status": "PASS",
        "failure_index": failure_index,
        "worker_count": chunks,
        "primary_valid_count": chunks - 1,
        "repaired_result_count": 1,
        "recovered_indexes": recovered_indexes,
        "primary_provider_counts": dict(primary_counts),
        "repair_provider_counts": dict(repair_counts),
        "execution_provider_ids": sorted(set(primary_counts) | set(repair_counts)),
        "cross_provider_closed": True,
        "combined_sum": aggregate_evidence["combined_sum"],
        "expected_sum": expected_total,
        "local_formal_compute_percent": 0,
        "github_primary_recomputed_count": 0,
    }


def _read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_results(results_dir: str) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(Path(results_dir).rglob("result-*.json"))
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--repair-plan", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--aggregate-evidence", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    evidence = verify_recovery(
        _read_json(args.plan),
        _read_json(args.repair_plan),
        _load_results(args.results_dir),
        _read_json(args.aggregate_evidence),
        args.run_id,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
