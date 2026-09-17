#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from compute_chunk import partition_range, sum_squares_formula
from plan_work import require_external_zero_cash_context, write_github_outputs


def _valid_primary(item: dict, assignment: dict, n: int, chunks: int, index: int) -> bool:
    try:
        start, end = partition_range(n, chunks, index)
        expected_provider = assignment["provider_id"]
        return (
            item.get("chunk_index") == index
            and item.get("chunks") == chunks
            and item.get("n") == n
            and item.get("range_start") == start
            and item.get("range_end") == end
            and item.get("partial_sum") == sum_squares_formula(start, end)
            and item.get("attempt", "primary") == "primary"
            and item.get("provider_id") == expected_provider
            and item.get("scheduled_provider_id") == expected_provider
            and item.get("repo_visibility") == "public"
            and item.get("runner_environment") == "github-hosted"
            and item.get("local_compute_used") is False
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return False


def build_repair_plan(plan: dict, primary_results: list[dict]) -> dict:
    n = int(plan["n"])
    chunks = int(plan["chunks"])
    assignments = plan["assignments"]
    if len(assignments) != chunks:
        raise RuntimeError("primary plan assignment count does not match chunks")
    by_assignment = {int(item["index"]): item for item in assignments}
    if set(by_assignment) != set(range(chunks)):
        raise RuntimeError("primary plan does not cover every shard exactly once")

    by_index: dict[int, list[dict]] = {index: [] for index in range(chunks)}
    for item in primary_results:
        index = item.get("chunk_index")
        if isinstance(index, int) and index in by_index:
            by_index[index].append(item)

    repair_indexes: list[int] = []
    for index in range(chunks):
        valid = [
            item
            for item in by_index[index]
            if _valid_primary(item, by_assignment[index], n, chunks, index)
        ]
        if len(valid) != 1:
            repair_indexes.append(index)

    provider_id = str(plan.get("repair_provider_id", "")).strip()
    budget = int(plan.get("repair_budgets", {}).get(provider_id, 0)) if provider_id else 0
    if not provider_id or budget < len(repair_indexes):
        raise RuntimeError("reserved repair budget cannot cover missing shards")

    repair_assignments = []
    for index in repair_indexes:
        original_provider_id = str(by_assignment[index]["provider_id"])
        if provider_id == original_provider_id:
            raise RuntimeError("repair provider must differ from original provider")
        repair_assignments.append(
            {
                "index": index,
                "original_provider_id": original_provider_id,
                "provider_id": provider_id,
            }
        )

    return {
        "repair_indexes": repair_indexes,
        "repair_count": len(repair_indexes),
        "repair_assignments": repair_assignments,
        "repair_provider_id": provider_id,
        "repair_budget": budget,
        "local_formal_compute_percent": 0,
    }


def _load_results(results_dir: Path) -> list[dict]:
    values = []
    for path in sorted(results_dir.rglob("result-*.json")):
        try:
            values.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args()

    require_external_zero_cash_context()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    repair = build_repair_plan(plan, _load_results(Path(args.results_dir)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(repair, indent=2, sort_keys=True), encoding="utf-8")
    if args.github_output:
        write_github_outputs(
            args.github_output,
            {
                "repair_count": repair["repair_count"],
                "repair_indexes": json.dumps(repair["repair_indexes"], separators=(",", ":")),
                "repair_assignments": json.dumps(repair["repair_assignments"], separators=(",", ":")),
            },
        )
    print(json.dumps(repair, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
