#!/usr/bin/env python3
import argparse
import json
import math
import os
from pathlib import Path


def choose_chunk_count(n: int, target_items_per_chunk: int, max_chunks: int) -> int:
    if n < 1:
        raise ValueError("n must be positive")
    if target_items_per_chunk < 1:
        raise ValueError("target_items_per_chunk must be positive")
    if max_chunks < 1:
        raise ValueError("max_chunks must be positive")
    return min(max_chunks, max(1, math.ceil(n / target_items_per_chunk)))


def require_external_zero_cash_context() -> None:
    checks = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "REPO_VISIBILITY": "public",
    }
    for key, expected in checks.items():
        actual = os.getenv(key, "")
        if actual != expected:
            raise RuntimeError(f"{key} must be {expected!r}, got {actual!r}")


def write_github_outputs(path: str, values: dict[str, object]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--target-items-per-chunk", type=int, required=True)
    parser.add_argument("--max-chunks", type=int, required=True)
    parser.add_argument("--fail-primary-index", type=int, default=-1)
    parser.add_argument("--output", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args()

    require_external_zero_cash_context()
    chunks = choose_chunk_count(args.n, args.target_items_per_chunk, args.max_chunks)
    if args.fail_primary_index >= chunks:
        raise ValueError("fail_primary_index must be -1 or a valid shard index")
    indexes = list(range(chunks))
    plan = {
        "n": args.n,
        "target_items_per_chunk": args.target_items_per_chunk,
        "max_chunks": args.max_chunks,
        "chunks": chunks,
        "indexes": indexes,
        "fail_primary_index": args.fail_primary_index,
        "local_formal_compute_percent": 0,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")

    if args.github_output:
        write_github_outputs(
            args.github_output,
            {
                "n": args.n,
                "chunks": chunks,
                "indexes": json.dumps(indexes, separators=(",", ":")),
                "fail_index": args.fail_primary_index,
            },
        )
    print(json.dumps(plan, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
