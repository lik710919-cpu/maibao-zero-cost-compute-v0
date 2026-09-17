#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from compute_chunk import partition_range, sum_squares_formula


def is_valid_primary(item: dict, expected_n: int, expected_chunks: int, expected_index: int) -> bool:
    try:
        start, end = partition_range(expected_n, expected_chunks, expected_index)
        return (
            item.get("chunk_index") == expected_index
            and item.get("chunks") == expected_chunks
            and item.get("n") == expected_n
            and item.get("range_start") == start
            and item.get("range_end") == end
            and item.get("partial_sum") == sum_squares_formula(start, end)
            and item.get("runner_environment") == "github-hosted"
            and item.get("repo_visibility") == "public"
            and item.get("local_compute_used") is False
            and item.get("attempt", "primary") == "primary"
        )
    except (TypeError, ValueError):
        return False


def find_repair_indexes(results_dir: Path, expected_n: int, expected_chunks: int) -> list[int]:
    by_index: dict[int, list[dict]] = {index: [] for index in range(expected_chunks)}
    for path in sorted(results_dir.rglob("result-*.json")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            index = int(item.get("chunk_index", -1))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if index in by_index:
            by_index[index].append(item)

    repairs = []
    for index in range(expected_chunks):
        valid = [
            item for item in by_index[index]
            if is_valid_primary(item, expected_n, expected_chunks, index)
        ]
        if len(valid) != 1:
            repairs.append(index)
    return repairs


def require_external_zero_cash_context() -> None:
    if os.getenv("GITHUB_ACTIONS") != "true":
        raise RuntimeError("repair planning must run in GitHub Actions")
    if os.getenv("RUNNER_ENVIRONMENT") != "github-hosted":
        raise RuntimeError("repair planning must run on GitHub-hosted compute")
    if os.getenv("REPO_VISIBILITY") != "public":
        raise RuntimeError("repair planning requires a public repository")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--chunks", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args()

    require_external_zero_cash_context()
    repairs = find_repair_indexes(Path(args.results_dir), args.n, args.chunks)
    matrix_indexes = repairs if repairs else [-1]
    evidence = {
        "expected_chunks": args.chunks,
        "repair_indexes": repairs,
        "repair_count": len(repairs),
        "matrix_indexes": matrix_indexes,
        "local_formal_compute_percent": 0,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")

    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(f"indexes={json.dumps(matrix_indexes, separators=(',', ':'))}\n")
            handle.write(f"repair_count={len(repairs)}\n")
            handle.write(f"repair_indexes={json.dumps(repairs, separators=(',', ':'))}\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
