# V5 Adaptive Multiprovider Pool Plan

1. Add red tests for capacity/budget-aware shard scheduling.
2. Implement a deterministic capacity scheduler.
3. Add a pool planner that chooses shard count, probes providers once, applies provider budgets, and emits a matrix.
4. Add an assigned-provider shard executor that performs no provider re-routing and never calls unassigned providers.
5. Add pool-evidence verification comparing scheduler assignments with actual result providers.
6. Add a V5 workflow with plan, parallel execution matrix, aggregate, catalog, and evidence upload.
7. Acceptance target: 8 auto-selected shards, exactly 1 Wandbox formal shard, 7 GitHub-hosted shards, 0% local formal compute.
8. Run branch acceptance and require correct merged result plus two real execution providers.
9. Review, fast-forward/merge to main without force, and run a fresh main acceptance.
10. Permanently record closure while retaining control-plane independence and additional-provider expansion as future gates.
