# Zero-Cash-Cost Compute V5: Adaptive Multiprovider Pool

## Goal
Combine automatic task splitting with provider-aware scheduling so one workload is automatically divided into multiple shards and distributed across the currently usable zero-cash-cost external provider pool.

## Acceptance providers
- `github-actions-public`: scalable hosted-runner provider for the experiment.
- `wandbox-public`: low-load shared fallback/secondary provider, capped at one formal shard per acceptance run.

## Planner
1. Choose shard count from workload size, target shard size, and maximum shard count.
2. Probe provider readiness once in the plan stage.
3. Build provider policies with capacity and per-run usage budget.
4. Assign every shard exactly once using projected normalized load: `(assigned + 1) / capacity`.
5. Respect per-provider task budgets before comparing load.
6. Emit a deterministic assignment matrix as execution evidence.

## Acceptance policy
For 8 shards with GitHub capacity 4 and Wandbox capacity 1 / max 1 task:
- exactly 1 shard must be assigned to Wandbox;
- the other 7 shards must be assigned to GitHub-hosted external runners;
- Wandbox must receive only one formal compute request;
- no local formal compute is permitted.

## Execution
Each matrix job executes only its scheduler-assigned provider. GitHub-assigned jobs do not probe or call Wandbox. The single Wandbox-assigned job performs one remote Wandbox execution request.

## Verification
Final verification must prove:
- automatic shard count was used;
- every shard index is assigned exactly once;
- provider budgets were respected;
- returned provider identity matches scheduler assignment;
- all shard ranges cover the task exactly once;
- final merged result equals the independent closed-form result;
- at least two real providers executed the same logical task;
- local formal compute is 0%.

## Scope boundary
V5 proves adaptive multi-shard scheduling across two real external providers. It does not yet prove orchestration/control-plane survival if GitHub Actions is unavailable, and it does not treat Wandbox as a high-volume production provider.
