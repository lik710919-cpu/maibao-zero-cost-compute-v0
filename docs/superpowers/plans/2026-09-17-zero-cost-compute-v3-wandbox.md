# V3 Real Two-Provider Implementation Plan

1. Add red tests for provider-aware aggregation and Wandbox response handling.
2. Add `wandbox_chunk.py` that submits exactly one remote Python computation to Wandbox and writes a normalized result file.
3. Extend result validation to accept explicit provider IDs while preserving all V1 GitHub checks.
4. Extend aggregation evidence with `execution_provider_ids`, provider count, and cross-provider closure.
5. Extend provider probing to recognize Wandbox only when a real V3 execution evidence file is present.
6. Add a dedicated V3 workflow: one GitHub shard, one Wandbox shard, external aggregate/verify, provider catalog evidence.
7. Run branch acceptance. Require two distinct provider IDs and correct combined result.
8. Review changes, merge to `main`, and run one fresh main-branch V3 acceptance.
9. Write permanent closure evidence. Do not claim broader production pool completion beyond the proven two-provider path.
