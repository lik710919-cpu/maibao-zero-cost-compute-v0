# Zero-Cash-Cost Compute V4: Automatic Routing and Failover

## Goal
Move from fixed provider assignment to runtime provider selection and task-level failover while preserving local formal compute at 0%.

## Proven providers available to V4
- `github-actions-public`: primary external provider for this acceptance.
- `wandbox-public`: low-load best-effort fallback provider proven by V3.

## Routing rule
Use the provider router to rank eligible zero-cash-cost providers by queue time, then capacity. The dispatcher receives the ordered provider list and attempts providers in that order.

## Failover rule
For each shard:
1. attempt the primary provider;
2. if the provider fails before a valid result is produced, record the failed attempt;
3. move to the next eligible provider exactly once;
4. validate the returned shard before accepting it;
5. fail closed if no provider succeeds.

## Acceptance
Use two shards for one deterministic task:
- shard 0 follows the normal route and should execute on the primary provider;
- shard 1 injects a controlled primary-provider failure before formal compute, forcing automatic fallback to Wandbox.

Final evidence must prove:
- no fixed provider assignment in the shard command;
- route primary and fallback are generated from provider snapshots;
- one shard uses the primary and one uses the fallback after a recorded primary failure;
- both results merge correctly;
- local formal compute remains 0%;
- two-provider same-task closure remains true.

## Scope boundary
This proves task-level provider failover while GitHub Actions is still the orchestration/control plane. It does not prove control-plane survival if GitHub Actions itself is unavailable.

## Shared-service guard
Wandbox remains a low-load experimental fallback only. One formal Wandbox shard per acceptance run, small synthetic workload, no secrets or production data, and fail closed on service rejection or rate limiting.
