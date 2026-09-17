#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def sum_squares_upto(value: int) -> int:
    if value <= 0:
        return 0
    return value * (value + 1) * (2 * value + 1) // 6


def sum_squares_formula(start: int, end: int) -> int:
    return sum_squares_upto(end) - sum_squares_upto(start - 1)


def partition_range(n: int, chunks: int, index: int) -> tuple[int, int]:
    base, remainder = divmod(n, chunks)
    size = base + (1 if index < remainder else 0)
    start = 1 + index * base + min(index, remainder)
    return start, start + size - 1


def fail(message: str) -> None:
    raise RuntimeError(message)


def is_valid_result(item: dict, expected_n: int, expected_chunks: int, expected_index: int) -> bool:
    try:
        start, end = partition_range(expected_n, expected_chunks, expected_index)
        attempt = item.get("attempt", "primary")
        return (
            item.get("chunk_index") == expected_index
            and item.get("chunks") == expected_chunks
            and item.get("n") == expected_n
            and item.get("range_start") == start
            and item.get("range_end") == end
            and item.get("partial_sum") == sum_squares_formula(start, end)
            and attempt in {"primary", "repair"}
            and item.get("runner_environment") == "github-hosted"
            and item.get("repo_visibility") == "public"
            and item.get("local_compute_used") is False
        )
    except (TypeError, ValueError, ZeroDivisionError):
        return False


def verify_results(result_paths: list[Path], expected_n: int | None = None, expected_chunks: int | None = None) -> dict:
    loaded = []
    for path in result_paths:
        try:
            loaded.append(json.loads(Path(path).read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            fail(f"invalid result file {path}: {exc}")
    if not loaded:
        fail("no worker results found")

    if expected_n is None:
        n_values = {item.get("n") for item in loaded}
        if len(n_values) != 1:
            fail("workers disagree about n")
        expected_n = n_values.pop()
    if expected_chunks is None:
        chunk_values = {item.get("chunks") for item in loaded}
        if len(chunk_values) != 1:
            fail("workers disagree about chunk count")
        expected_chunks = chunk_values.pop()
    if not isinstance(expected_n, int) or expected_n < 1:
        fail("invalid expected n")
    if not isinstance(expected_chunks, int) or expected_chunks < 1:
        fail("invalid expected chunk count")

    by_index: dict[int, list[dict]] = {index: [] for index in range(expected_chunks)}
    for item in loaded:
        index = item.get("chunk_index")
        if isinstance(index, int) and index in by_index:
            by_index[index].append(item)

    chosen = []
    recovered_indexes = []
    for index in range(expected_chunks):
        valid = [
            item for item in by_index[index]
            if is_valid_result(item, expected_n, expected_chunks, index)
        ]
        repairs = [item for item in valid if item.get("attempt", "primary") == "repair"]
        primaries = [item for item in valid if item.get("attempt", "primary") == "primary"]
        if len(repairs) > 1 or len(primaries) > 1:
            fail(f"duplicate valid results for chunk {index}")
        if repairs:
            chosen.append(repairs[0])
            recovered_indexes.append(index)
        elif primaries:
            chosen.append(primaries[0])
        else:
            fail(f"missing or invalid result for chunk {index}")

    chosen.sort(key=lambda item: item["chunk_index"])
    expected_start = 1
    combined = 0
    for item in chosen:
        if item["range_start"] != expected_start:
            fail(f"range coverage failure at chunk {item['chunk_index']}")
        expected_start = item["range_end"] + 1
        combined += item["partial_sum"]
    if expected_start != expected_n + 1:
        fail("worker ranges do not cover 1..N exactly")

    expected_total = sum_squares_formula(1, expected_n)
    if combined != expected_total:
        fail("combined result does not equal closed-form result")

    hostnames = sorted({item.get("hostname", "") for item in chosen})
    runner_names = sorted({item.get("runner_name", "") for item in chosen})
    primary_valid_count = sum(1 for item in chosen if item.get("attempt", "primary") == "primary")
    repaired_result_count = len(recovered_indexes)
    return {
        "status": "PASS",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "formal_compute_location": "external-github-hosted-only",
        "local_formal_compute_percent": 0,
        "repository_visibility": "public",
        "automatic_chunk_count": expected_chunks,
        "worker_count": len(chosen),
        "primary_valid_count": primary_valid_count,
        "repaired_result_count": repaired_result_count,
        "recovered_indexes": recovered_indexes,
        "n": expected_n,
        "combined_sum": combined,
        "expected_sum": expected_total,
        "unique_hostnames": hostnames,
        "unique_hostname_count": len(hostnames),
        "unique_runner_names": runner_names,
        "unique_runner_name_count": len(runner_names),
        "workers": chosen,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-n", type=int)
    parser.add_argument("--expected-chunks", type=int)
    args = parser.parse_args()

    result_paths = sorted(Path(args.results_dir).rglob("result-*.json"))
    evidence = verify_results(result_paths, args.expected_n, args.expected_chunks)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "verification.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
    )

    lines = [
        "# Zero-Cash-Cost External Compute Verification",
        "",
        "- Status: PASS",
        "- Local formal compute: 0%",
        "- Formal compute: GitHub-hosted external runners only",
        "- Repository visibility: public",
        f"- Automatic chunk count: {evidence['automatic_chunk_count']}",
        f"- Primary valid results: {evidence['primary_valid_count']}",
        f"- Repaired results: {evidence['repaired_result_count']}",
        f"- Recovered indexes: {evidence['recovered_indexes']}",
        f"- N: {evidence['n']}",
        f"- Combined sum: {evidence['combined_sum']}",
        f"- Expected sum: {evidence['expected_sum']}",
        f"- Unique runner names observed: {evidence['unique_runner_name_count']}",
        "",
        "## Worker evidence",
    ]
    for item in evidence["workers"]:
        lines.append(
            f"- chunk {item['chunk_index']}: {item['range_start']}..{item['range_end']}; "
            f"attempt={item.get('attempt', 'primary')}; runner={item.get('runner_name', '')}; "
            f"duration={item.get('duration_seconds', 0)}s"
        )
    (output_dir / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
