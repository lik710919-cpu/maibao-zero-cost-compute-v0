#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path


def verify_pool(plan: dict, results: list[dict]) -> dict:
    assignments = plan.get("assignments", [])
    expected_chunks = int(plan.get("chunks", 0))
    if expected_chunks < 1 or len(assignments) != expected_chunks:
        raise RuntimeError("invalid pool plan shard count")
    if len(results) != expected_chunks:
        raise RuntimeError("result count does not match pool plan")

    expected_by_index = {item["index"]: item["provider_id"] for item in assignments}
    if len(expected_by_index) != expected_chunks:
        raise RuntimeError("pool plan contains duplicate shard indexes")

    actual_by_index: dict[int, dict] = {}
    for result in results:
        index = result.get("chunk_index")
        if index in actual_by_index:
            raise RuntimeError("duplicate shard result")
        actual_by_index[index] = result

    if set(actual_by_index) != set(expected_by_index):
        raise RuntimeError("returned shard indexes do not match pool plan")

    actual_counts: Counter[str] = Counter()
    for index, expected_provider in expected_by_index.items():
        result = actual_by_index[index]
        if result.get("scheduled_provider_id") != expected_provider:
            raise RuntimeError("scheduled provider identity mismatch")
        if result.get("provider_id") != expected_provider:
            raise RuntimeError("executing provider identity mismatch")
        if result.get("local_compute_used") is not False:
            raise RuntimeError("local formal compute was used")
        actual_counts[expected_provider] += 1

    expected_counts = plan.get("assignment_counts", {})
    if dict(actual_counts) != expected_counts:
        raise RuntimeError("provider assignment counts do not match plan")

    return {
        "status": "PASS",
        "worker_count": expected_chunks,
        "provider_count": len(actual_counts),
        "execution_provider_ids": sorted(actual_counts),
        "assignment_counts": dict(actual_counts),
        "local_formal_compute_percent": 0,
    }


def load_results(results_dir: Path) -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(results_dir.glob("result-*.json"))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    report = verify_pool(plan, load_results(Path(args.results_dir)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
