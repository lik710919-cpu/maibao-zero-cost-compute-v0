# Zero-Cash-Cost Compute V3: Real Two-Provider Design

## Goal
Prove one logical task can execute across two distinct external zero-cash-cost providers and be merged with local formal compute remaining 0%.

## Providers
1. `github-actions-public`: public GitHub-hosted runner.
2. `wandbox-public`: Wandbox public compile/execute API, used only within published service limits.

## Truth rules
- A provider is live only with real execution evidence.
- `cross_provider_closed` is true only if the same logical task has valid result shards from at least two distinct provider IDs.
- The GitHub runner used to submit a Wandbox request is control-plane only; the Wandbox shard's formal compute must occur remotely at Wandbox.
- No unproven candidate is promoted.
- No local machine formal compute is allowed.

## V3 proof
Split a deterministic sum-of-squares task into two shards:
- shard 0: computed on GitHub-hosted runner;
- shard 1: submitted to Wandbox and computed remotely.

Both result files must pass the same range, closed-form, and coverage checks. Final evidence must show two execution provider IDs and `cross_provider_closed=true`.

## Safety and load
- Use a small synthetic workload only.
- Make one Wandbox execution request per proof run.
- Do not upload secrets or production data.
- Treat Wandbox as best-effort/no-SLA; failure must fail closed and must not silently fall back while claiming two-provider closure.
