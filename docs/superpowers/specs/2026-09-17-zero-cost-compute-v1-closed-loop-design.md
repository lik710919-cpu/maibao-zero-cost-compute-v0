# Zero-Cash-Cost External Compute V1 Closed-Loop Design

## Goal
Upgrade the proven V0 experiment into a self-healing external compute loop: automatic shard sizing, distributed primary execution, automatic detection and recomputation of missing/invalid shards, external aggregation, deterministic verification, and permanent evidence.

## Frozen constraints
- Local machine remains ignition/control only and contributes 0% of formal computation.
- Repository remains public and contains only synthetic, non-sensitive workload code/data.
- Cash cost for the acceptance run must remain 0.
- Only standard GitHub-hosted runners are used.
- No paid cloud resources, larger runners, secrets, production code, or private data.
- Failure of one primary shard must not fail the overall task if a replacement shard can complete it.

## Architecture
1. An external planner job selects shard count from N, target items per shard, and a maximum shard cap, then emits a matrix.
2. Primary worker jobs execute the generated matrix on GitHub-hosted runners and upload one result artifact per successful shard.
3. The acceptance run deliberately interrupts one selected primary shard before computation, proving recovery rather than only the happy path.
4. An external repair-planner job downloads available primary artifacts, validates them, identifies missing/invalid shard indexes, and emits only those indexes for repair.
5. Repair workers recompute only missing/invalid shards on GitHub-hosted runners.
6. An external aggregator downloads primary and repair results, requires exact 1..N coverage, validates every partial result, verifies the combined result against the closed-form formula, and emits evidence.

## Automatic shard policy
`chunk_count = min(max_chunks, max(1, ceil(N / target_items_per_chunk)))`.

The default acceptance values are N=40,000,000, target_items_per_chunk=5,000,000, max_chunks=16, producing 8 shards automatically. The workflow may be dispatched with different values without editing code.

## Failure and recovery model
A primary result is reusable only when its index, chunk count, N, range, result, public-repository marker, GitHub-hosted marker, and local-compute marker are valid. Missing or invalid primary results are treated as repair candidates. Repair workers produce authoritative replacement artifacts for those indexes.

The acceptance run injects failure into primary shard 2. A successful V1 acceptance therefore requires at least one repair shard and a final PASS.

## Evidence requirements
Final evidence must record status, N, automatic chunk count, primary valid result count, repaired result count, recovered indexes, combined and expected totals, local formal compute percent, repository visibility, unique runner names, workflow run identifiers, and worker-level evidence.

## V1 success criterion
V1 is closed only when a real workflow-dispatch run on the merged/default-branch implementation uses an automatically generated shard count, intentionally loses primary shard 2, automatically detects and recomputes it externally, completes aggregation successfully, proves local formal compute is 0%, proves combined equals expected, and stores both retrievable artifact evidence and a permanent repository-side closure record.
