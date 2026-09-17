#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from plan_work import choose_chunk_count, require_external_zero_cash_context, write_github_outputs
from provider_model import ProviderSnapshot
from routed_chunk import build_runtime_route

PRIMARY_PROVIDER_ID = "github-actions-public"
REPAIR_PROVIDER_ID = "wandbox-public"
FAILURE_INDEX = 4


def _eligible(snapshot: ProviderSnapshot) -> bool:
    return (
        snapshot.authorized
        and snapshot.healthy
        and snapshot.zero_cash_cost
        and snapshot.capacity > 0
        and bool(str(snapshot.evidence).strip())
        and snapshot.evidence != "none"
    )


def build_recovery_plan(
    n: int,
    target_items_per_chunk: int,
    max_chunks: int,
    compiler: str,
    providers: list[ProviderSnapshot],
) -> dict:
    by_id = {item.provider_id: item for item in providers}
    primary = by_id.get(PRIMARY_PROVIDER_ID)
    repair = by_id.get(REPAIR_PROVIDER_ID)
    if primary is None or not _eligible(primary):
        raise RuntimeError("GitHub primary provider is not eligible")
    if repair is None or not _eligible(repair):
        raise RuntimeError("Wandbox repair provider is not eligible")

    chunks = choose_chunk_count(n, target_items_per_chunk, max_chunks)
    if chunks <= FAILURE_INDEX:
        raise RuntimeError("V6 acceptance requires a shard at failure index 4")

    assignments = [
        {"index": index, "provider_id": PRIMARY_PROVIDER_ID}
        for index in range(chunks)
    ]
    return {
        "n": n,
        "target_items_per_chunk": target_items_per_chunk,
        "max_chunks": max_chunks,
        "chunks": chunks,
        "assignments": assignments,
        "assignment_counts": {PRIMARY_PROVIDER_ID: chunks},
        "failure_index": FAILURE_INDEX,
        "repair_provider_id": REPAIR_PROVIDER_ID,
        "repair_budgets": {REPAIR_PROVIDER_ID: 1},
        "compiler": compiler,
        "local_formal_compute_percent": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--target-items-per-chunk", type=int, required=True)
    parser.add_argument("--max-chunks", type=int, required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args()

    require_external_zero_cash_context()
    _, snapshots = build_runtime_route(args.compiler)
    plan = build_recovery_plan(
        args.n,
        args.target_items_per_chunk,
        args.max_chunks,
        args.compiler,
        snapshots,
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
                "failure_index": plan["failure_index"],
                "assignments": json.dumps(plan["assignments"], separators=(",", ":")),
                "repair_provider_id": plan["repair_provider_id"],
            },
        )
    print(json.dumps(plan, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
