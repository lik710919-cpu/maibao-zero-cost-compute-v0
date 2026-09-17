# V8 GitLab Adapter Design

## Goal
Convert the V7-selected GitLab hosted runner candidate into a production-ready provider adapter that can be activated as soon as an authorized GitLab project and credentials are supplied.

V8 must preserve the frozen constraints: local control only, zero new cash cost, legal/authorized use, real external execution proof, and fail-closed cost control.

## External facts used by the design
- GitLab.com Free namespaces receive 400 compute minutes per month on instance runners.
- Pipelines can be triggered through the pipeline trigger API.
- Pipeline status and jobs can be read through the REST API.
- Job artifacts can carry formal compute results back to the control plane.
- Standard GitLab.com Linux small hosted runners have compute cost factor 1.
- Purchased additional minute packs can be consumed after the monthly allocation, so the adapter must keep an internal safety reserve rather than intentionally run to the platform quota boundary.

## Authentication
Use two least-purpose credentials:
1. A pipeline trigger token used only to dispatch work.
2. A read-only API token used only for pipeline/job status and artifact retrieval.

No credential is stored in the repository or evidence artifacts. The controller reads credentials from environment variables at runtime.

## Cost guard
The adapter never treats all 400 minutes as dispatchable. Configuration requires:
- declared monthly free quota,
- declared starting monthly usage or trusted usage snapshot,
- reserve minutes,
- per-shard maximum runtime.

Before dispatch, the controller computes a conservative projected usage. If the projected usage would cross the safe budget, dispatch is rejected before any external job starts.

A live activation is not valid until the namespace is confirmed as an authorized Free namespace and the baseline usage is recorded. The adapter must not attempt to create or rotate extra accounts or namespaces to evade quota limits.

## Dispatch contract
A shard dispatch contains only validated structured inputs:
- shard index,
- range start,
- range end,
- task kind,
- task nonce.

The controller sends these as pipeline inputs or trigger variables. The trigger response pipeline ID becomes the immutable execution reference.

## Worker contract
The GitLab project contains a minimal worker job that:
- validates the shard contract,
- executes the supported deterministic computation,
- writes one JSON result artifact,
- records GitLab pipeline/job identity and provider identity,
- never calls back to the local machine.

The initial supported formal task is the same deterministic sum-of-squares style shard computation already used by the existing pool, so cross-provider result verification can reuse existing semantics.

## Result collection
The controller:
1. polls the specific pipeline until terminal state,
2. lists jobs for that pipeline,
3. identifies the formal compute job,
4. downloads its result artifact,
5. validates provider identity, shard boundaries, nonce, and result,
6. emits normalized evidence for the existing aggregation layer.

## Fail-closed behavior
The adapter refuses dispatch when:
- credentials are missing,
- project ID/ref is missing,
- budget state is missing or unsafe,
- shard bounds are invalid,
- the pipeline cannot be tied to the returned pipeline ID,
- the formal job does not succeed,
- the result identity or nonce does not match,
- the artifact is malformed.

## Activation stages
### Stage A: code-ready
Tests, request construction, budget guard, result validation, worker template, and dry-run evidence are green in GitHub.

### Stage B: live provider activation
Requires an authorized GitLab project plus runtime credentials. A real GitLab-hosted job must execute one formal shard and return a verified artifact. Only then is `gitlab-hosted-runners` promoted from adapter-ready to active pool provider.

## Next-use rule
Once the first live shard is verified, GitLab is immediately added to the provider catalog with a conservative per-run budget. The existing capacity scheduler can then assign bounded formal shards to it, and V6 cross-provider repair remains available around it.
