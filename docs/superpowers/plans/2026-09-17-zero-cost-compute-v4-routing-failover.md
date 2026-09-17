# V4 Automatic Routing and Failover Plan

1. Add red tests for ordered provider attempts, primary failure fallback, and fail-closed exhaustion.
2. Add a provider-agnostic shard dispatcher with injectable provider executors.
3. Add real GitHub and Wandbox executor adapters using the existing validated result schema.
4. Record routing and attempt evidence in every result.
5. Add a dedicated V4 workflow that constructs the provider route at runtime.
6. Execute shard 0 normally and shard 1 with a controlled primary failure.
7. Aggregate both shards and verify same-task cross-provider closure.
8. Require one and only one Wandbox formal shard per acceptance run.
9. Run branch acceptance, review, merge to main, and run a fresh main acceptance.
10. Write permanent closure evidence and explicitly retain the control-plane failover gap for the next stage.
