# V9 Policy-Aware Capacity Growth Implementation Plan

## Objective
Teach the growth engine to separate advertised free capacity from policy-safe formal pool capacity, then use that distinction to choose the next research and adapter targets without overstating capacity.

## Task 1: Define failing policy-gate tests
Add tests that require:
- CircleCI open-source capacity to remain behind a policy gate for general formal compute.
- GitHub Codespaces to be classified as a developer environment, not general formal compute.
- Bitbucket Free and Azure DevOps private free grant to remain manual-gated.
- unresolved terms scope to fail closed regardless of advertised capacity.
- growth reports to keep advertised capacity separate from active capacity.

## Task 2: Extend candidate model and qualification
Add policy-scope fields and a `policy_gate` qualification state without weakening existing cost/authorization behavior.

## Task 3: Expand evidence-backed candidate registry
Add CircleCI, GitHub Codespaces, Bitbucket Pipelines, and Azure DevOps Pipelines with current official evidence and conservative classifications.

## Task 4: Add policy-aware prioritization
Generate separate lists for formal pool, project-native CI, developer environment, policy gate, and manual gate candidates.

Only policy-safe candidates may become `next_adapter_target`. A large but unresolved candidate may become `next_research_target` instead.

## Task 5: Add continuous acceptance
Run the full unit suite and emit a V9 artifact proving:
- no unresolved-policy candidate is counted as active or auto-eligible formal capacity;
- local formal compute remains zero;
- next research and adapter targets are explicitly distinguished.

## Completion criteria
- Red/green TDD evidence exists.
- Full regression suite passes.
- V9 evidence artifact is produced.
- V9 merges to main.
- The output immediately drives the next research/adapter cycle.
