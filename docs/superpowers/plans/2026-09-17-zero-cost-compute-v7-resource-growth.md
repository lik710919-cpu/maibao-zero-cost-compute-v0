# V7 Resource Growth Implementation Plan

## Objective
Convert researched free-compute opportunities into a fail-closed qualification pipeline that immediately identifies the next safe provider-integration target.

## Task 1: Define qualification contract
1. Add tests for candidate classification.
2. Verify the tests fail because the qualification module does not yet exist.
3. Required cases:
   - GitLab-like hard-quota free compute -> `auto_eligible`.
   - Modal/Cloud Run-like metered overage -> `manual_gate`.
   - Cloudflare Workers-like tiny CPU budget -> `control_only`.
   - unknown authorization/cost behavior -> `research_only`.

## Task 2: Implement candidate model and qualification
1. Add the smallest production module that satisfies the tests.
2. Default missing safety facts to fail-closed.
3. Keep policy data separate from dispatch code.

## Task 3: Add evidence-backed seed registry
1. Add machine-readable provider candidate data.
2. Include source URL, research date, quota summary, cost-exposure flags, and activation notes.
3. Do not store credentials or account identifiers.

## Task 4: Produce growth report
1. Add a CLI that reads the registry and emits JSON evidence.
2. Report candidates grouped by qualification state.
3. Require at least one next-adapter candidate.

## Task 5: Continuous acceptance
1. Add a V7 workflow on the V7 branch and main.
2. Run the full existing unit suite first.
3. Run V7 qualification and upload an evidence artifact.
4. Merge only after all tests are green.

## Completion criteria
- V1-V6 regression suite passes.
- V7 tests pass.
- Evidence artifact identifies the next adapter target without enabling any provider that could create unbounded cash cost.
- V7 is merged to main and therefore available to drive the next expansion cycle.
