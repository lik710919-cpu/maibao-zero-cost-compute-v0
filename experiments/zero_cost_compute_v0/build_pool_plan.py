#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from capacity_scheduler import ProviderPolicy, assign_shards, assignment_counts
from plan_work import choose_chunk_count, require_external_zero_cash_context, write_github_outputs
from routed_chunk import build_runtime_route


def build_plan(
    n: int,
    target_items_per_chunk: int,
    max_chunks: int,
    policies: list[ProviderPolicy],
    require_provider_count: int,
    compiler: str,
) -> dict:
    if require_provider_count < 1:
        raise ValueError("require_provider_count must be positive")
    provider_ids = [policy.provider_id for policy in policies]
    if len(provider_ids) < require_provider_count:
        raise RuntimeError("not enough eligible providers for requested pool")

    chunks = choose_chunk_count(n, target_items_per_chunk, max_chunks)
    assignments = assign_shards(chunks, policies)
    return {
        "n": n,
        "target_items_per_chunk": target_items_per_chunk,
        "max_chunks": max_chunks,
        "chunks": chunks,
        "assignments": assignments,
        "assignment_counts": assignment_counts(assignments),
        "provider_count": len(provider_ids),
        "provider_ids": provider_ids,
        "compiler": compiler,
        "local_formal_compute_percent": 0,
    }


def runtime_policies(compiler: str) -> list[ProviderPolicy]:
    route, snapshots = build_runtime_route(compiler)
    ordered_ids = [route["primary"], *route["fallbacks"]]
    by_id = {item.provider_id: item for item in snapshots}
    policies: list[ProviderPolicy] = []
    for priority, provider_id in enumerate(ordered_ids):
        snapshot = by_id[provider_id]
        max_tasks = 1 if provider_id == "wandbox-public" else None
        policies.append(
            ProviderPolicy(
                provider_id=provider_id,
                capacity=max(1, snapshot.capacity),
                max_tasks_per_run=max_tasks,
                priority=priority,
            )
        )
    return policies


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--target-items-per-chunk", type=int, required=True)
    parser.add_argument("--max-chunks", type=int, required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--require-provider-count", type=int, default=2)
    parser.add_argument("--output", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args()

    require_external_zero_cash_context()
    plan = build_plan(
        n=args.n,
        target_items_per_chunk=args.target_items_per_chunk,
        max_chunks=args.max_chunks,
        policies=runtime_policies(args.compiler),
        require_provider_count=args.require_provider_count,
        compiler=args.compiler,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    if args.github_output:
        write_github_outputs(
            args.github_output,
            {
                "n": plan["n"],
                "chunks": plan["chunks"],
                "assignments": json.dumps(plan["assignments"], separators=(",", ":")),
            },
        )
    print(json.dumps(plan, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
