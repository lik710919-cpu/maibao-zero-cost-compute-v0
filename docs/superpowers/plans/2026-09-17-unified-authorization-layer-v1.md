# Unified Authorization Layer V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable authorization core where one user authorization persists until explicit revocation, while short-lived/provider-specific runtime credentials can refresh or rebuild automatically; GitLab is the first adapter and the design remains reusable for a second provider without modifying the core.

**Architecture:** `AuthorizationCore` owns provider-neutral state transitions and orchestration. `ProviderAuthAdapter` contains provider-specific authorization behavior, `CredentialVault` stores secrets behind opaque references, `AuthorizationRegistry` stores only non-secret metadata, and `CapabilityActivator` converts an authorized provider into verified usable compute. GitLab initially delegates interactive account authorization to the official `glab auth login --device` flow and uses the authenticated CLI/API context to create/repair scoped runtime credentials without exposing the user token to repository files or logs.

**Tech Stack:** Python 3 standard library, `unittest`, GitLab CLI (`glab`) for GitLab.com OAuth device authorization, GitLab REST API, Windows Credential Manager adapter for local production, GitHub Actions for remote non-secret regression tests.

**Spec:** `docs/superpowers/specs/2026-09-17-unified-authorization-layer-v1-design.md`

## Global Constraints

- One authorization must remain usable until the user explicitly revokes it, except when the provider itself forces interactive reauthorization.
- Access-token expiry, runtime-token expiry, or transient provider failure must not silently become user revocation.
- Plaintext passwords, OAuth tokens, refresh tokens, and runtime secrets must never be committed to Git, ordinary logs, or evidence artifacts.
- Runtime credentials must use the minimum practical privilege and may be rotated/rebuilt independently of the user authorization relationship.
- Explicit user revocation has highest priority and must stop side effects, stop auto-refresh/rebuild, delete local secrets, and prevent automatic recovery.
- Provider-specific behavior must remain outside `AuthorizationCore`.
- Local compute remains control-only; formal compute stays external.

---

### Task 1: Provider-neutral authorization contracts and lifecycle

**Files:**
- Create: `experiments/zero_cost_compute_v0/authorization_core.py`
- Create: `experiments/zero_cost_compute_v0/tests/test_authorization_core.py`

**Interfaces:**
- Produces: `AuthorizationState`, `AuthorizationRecord`, `AuthorizationSession`, `ProviderAuthAdapter`, `CredentialVault`, `AuthorizationRegistry`, `AuthorizationCore`.
- `AuthorizationCore.status(provider_id: str) -> AuthorizationRecord | None`
- `AuthorizationCore.begin(provider_id: str) -> AuthorizationSession`
- `AuthorizationCore.poll(provider_id: str) -> AuthorizationRecord`
- `AuthorizationCore.ensure_usable(provider_id: str) -> AuthorizationRecord`
- `AuthorizationCore.revoke(provider_id: str) -> AuthorizationRecord`

- [ ] **Step 1: Write failing lifecycle tests**

```python
class AuthorizationCoreTests(unittest.TestCase):
    def test_expired_runtime_credential_repairs_without_losing_user_authorization(self):
        core, adapter, vault, registry = build_core(runtime_valid=False, refreshable=True)
        record = core.ensure_usable("fake")
        self.assertEqual(record.state, AuthorizationState.AUTHORIZED)
        self.assertTrue(record.runtime_credential_ref)
        self.assertEqual(adapter.refresh_calls, 1)

    def test_transient_failure_degrades_but_does_not_revoke(self):
        core, adapter, vault, registry = build_core(provider_error=True)
        record = core.ensure_usable("fake")
        self.assertEqual(record.state, AuthorizationState.DEGRADED)
        self.assertFalse(record.revoked_by_user)

    def test_explicit_user_revoke_is_terminal_until_new_begin(self):
        core, adapter, vault, registry = build_core()
        revoked = core.revoke("fake")
        self.assertEqual(revoked.state, AuthorizationState.REVOKED_BY_USER)
        self.assertTrue(revoked.revoked_by_user)
        with self.assertRaises(RuntimeError):
            core.ensure_usable("fake")
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `python -m unittest experiments.zero_cost_compute_v0.tests.test_authorization_core -v`

Expected: import failure because `authorization_core` does not exist.

- [ ] **Step 3: Implement minimal provider-neutral core**

Use enum states exactly from the spec and protocols/abstract methods with no GitLab fields:

```python
class AuthorizationState(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    AUTHORIZING = "AUTHORIZING"
    AUTHORIZED = "AUTHORIZED"
    REFRESHING = "REFRESHING"
    DEGRADED = "DEGRADED"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"
    REVOKED_BY_USER = "REVOKED_BY_USER"
```

`ensure_usable()` rules:
1. reject `REVOKED_BY_USER`;
2. validate user authorization;
3. if user auth is valid but runtime credential is missing/invalid, refresh/rebuild automatically;
4. provider-transient errors produce `DEGRADED`, not revocation;
5. only an adapter result explicitly declaring interactive authorization required produces `REAUTH_REQUIRED`.

- [ ] **Step 4: Run lifecycle tests and full suite**

Run:
`python -m unittest experiments.zero_cost_compute_v0.tests.test_authorization_core -v`
`python -m unittest discover -s experiments/zero_cost_compute_v0/tests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add provider-neutral authorization lifecycle`

---

### Task 2: Non-secret authorization registry and replaceable credential vault

**Files:**
- Create: `experiments/zero_cost_compute_v0/authorization_storage.py`
- Create: `experiments/zero_cost_compute_v0/tests/test_authorization_storage.py`
- Modify: `experiments/zero_cost_compute_v0/authorization_core.py`

**Interfaces:**
- Produces: `JsonAuthorizationRegistry`, `MemoryCredentialVault`, `WindowsCredentialVault`.
- `CredentialVault.put(name: str, secret: str) -> str`
- `CredentialVault.get(ref: str) -> str`
- `CredentialVault.delete(ref: str) -> None`
- `CredentialVault.exists(ref: str) -> bool`
- `AuthorizationRegistry.get(provider_id: str) -> AuthorizationRecord | None`
- `AuthorizationRegistry.put(record: AuthorizationRecord) -> None`

- [ ] **Step 1: Write failing storage tests**

```python
def test_registry_never_serializes_secret_values():
    vault = MemoryCredentialVault()
    secret_ref = vault.put("fake/user", "super-secret")
    registry = JsonAuthorizationRegistry(path)
    registry.put(AuthorizationRecord(provider_id="fake", user_credential_ref=secret_ref, ...))
    text = path.read_text(encoding="utf-8")
    self.assertNotIn("super-secret", text)
    self.assertIn(secret_ref, text)


def test_vault_reference_is_opaque_and_round_trips():
    vault = MemoryCredentialVault()
    ref = vault.put("fake/runtime", "runtime-secret")
    self.assertNotIn("runtime-secret", ref)
    self.assertEqual(vault.get(ref), "runtime-secret")
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest experiments.zero_cost_compute_v0.tests.test_authorization_storage -v`

- [ ] **Step 3: Implement registry + vaults**

`JsonAuthorizationRegistry` writes only dataclass metadata as JSON. `MemoryCredentialVault` is test-only. `WindowsCredentialVault` uses Windows Credential Manager via `ctypes` WinCred APIs and is imported safely on non-Windows systems without attempting Win32 calls.

The Windows vault target naming convention is `maibao-auth/<provider>/<purpose>` and returned refs are opaque `wincred:<target>` values.

- [ ] **Step 4: Verify tests and full suite**

Run storage test module, authorization core tests, then full suite.

- [ ] **Step 5: Commit**

Commit message: `feat: add authorization registry and credential vault`

---

### Task 3: GitLab device authorization adapter using official glab flow

**Files:**
- Create: `experiments/zero_cost_compute_v0/gitlab_auth_adapter.py`
- Create: `experiments/zero_cost_compute_v0/tests/test_gitlab_auth_adapter.py`

**Interfaces:**
- Produces: `GitLabAuthAdapter` implementing `ProviderAuthAdapter`.
- Interactive entry command: `glab auth login --hostname gitlab.com --device`.
- Status command: `glab auth status --hostname gitlab.com`.
- Authenticated API commands use `glab api` so the OAuth token stays in the OS keyring managed by `glab` and is never copied into repository metadata.

- [ ] **Step 1: Write failing adapter tests around command construction and redaction**

```python
def test_begin_authorization_uses_official_device_flow():
    adapter = GitLabAuthAdapter(runner=fake_runner)
    session = adapter.begin_authorization()
    self.assertEqual(fake_runner.calls[0], ["glab", "auth", "login", "--hostname", "gitlab.com", "--device"])
    self.assertEqual(session.provider_id, "gitlab")


def test_status_and_evidence_never_include_token():
    fake_runner.status_stdout = "Logged in to gitlab.com as user"
    result = adapter.validate_identity()
    self.assertNotIn("token", json.dumps(result).lower())
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest experiments.zero_cost_compute_v0.tests.test_gitlab_auth_adapter -v`

- [ ] **Step 3: Implement minimal adapter**

The adapter must:
- check `glab` availability/version;
- launch `glab auth login --hostname gitlab.com --device` for the initial user interaction;
- query `/user` through `glab api user` (or `/user`) for account identity;
- treat CLI/keyring-backed auth as the long-lived user authorization relationship;
- return structured non-secret status only;
- never call `glab auth status --show-token`.

Official GitLab docs confirm `--device` uses OAuth 2.0 Device Authorization Grant and `glab` defaults to OS keyring storage when a backend is available.

- [ ] **Step 4: Verify tests/full suite**

Run adapter test module and full suite.

- [ ] **Step 5: Commit**

Commit message: `feat: add GitLab device authorization adapter`

---

### Task 4: GitLab project registration and runtime credential bootstrap

**Files:**
- Modify: `experiments/zero_cost_compute_v0/gitlab_auth_adapter.py`
- Create: `experiments/zero_cost_compute_v0/tests/test_gitlab_runtime_bootstrap.py`
- Reuse: `experiments/zero_cost_compute_v0/gitlab_controller.py`
- Reuse: `.gitlab-ci.yml`

**Interfaces:**
- `GitLabAuthAdapter.ensure_project(project_name: str) -> dict`
- `GitLabAuthAdapter.create_runtime_credentials(project_id: str, vault: CredentialVault) -> dict[str, str]`
- Runtime output contains opaque vault refs plus non-secret IDs; it never returns secrets in evidence.

- [ ] **Step 1: Write failing API-contract tests**

Tests must prove:
- existing project is reused rather than duplicated;
- a missing project can be created under the authorized account/namespace;
- a Free-compatible pipeline trigger token is created via `POST /projects/:id/triggers` and immediately stored in the vault;
- trigger secret is removed from returned metadata before logging/evidence;
- reading pipeline/job/artifact status uses the OAuth-authenticated `glab api` path when GitLab.com Free cannot provide a project access token;
- no Premium-only project-access-token assumption is required.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest experiments.zero_cost_compute_v0.tests.test_gitlab_runtime_bootstrap -v`

- [ ] **Step 3: Implement GitLab.com Free-compatible bootstrap**

Use OAuth-backed `glab api` for read/status operations and project management. Use the pipeline trigger token only for formal dispatch. Store the trigger token in `CredentialVault`; store only trigger ID and vault ref in registry metadata.

Do not attempt to create a GitLab.com project access token on Free, because GitLab documents project access tokens on GitLab.com as Premium/Ultimate-only.

- [ ] **Step 4: Verify tests/full suite**

Run runtime bootstrap test module and full suite.

- [ ] **Step 5: Commit**

Commit message: `feat: bootstrap GitLab runtime credentials from persistent authorization`

---

### Task 5: Capability activation and explicit revocation

**Files:**
- Create: `experiments/zero_cost_compute_v0/capability_activator.py`
- Create: `experiments/zero_cost_compute_v0/tests/test_capability_activator.py`
- Modify: `experiments/zero_cost_compute_v0/provider_candidates.json`
- Modify: `experiments/zero_cost_compute_v0/resource_growth.py`

**Interfaces:**
- `CapabilityActivator.activate(provider_id: str) -> dict`
- `AuthorizationCore.revoke(provider_id: str) -> AuthorizationRecord`

- [ ] **Step 1: Write failing activation/revocation tests**

Tests require:
- activation refuses `UNAUTHORIZED`, `AUTHORIZING`, `DEGRADED`, `REAUTH_REQUIRED`, and `REVOKED_BY_USER`;
- authorized GitLab obtains/repairs runtime credential, executes one bounded formal shard, verifies result identity, and returns `live_active=true` only after evidence passes;
- explicit revoke deletes runtime secret, asks adapter to revoke remote trigger when possible, preserves a non-secret audit record, and blocks future auto-repair.

- [ ] **Step 2: Verify RED**

Run activation test module.

- [ ] **Step 3: Implement activator + registry transition**

On verified GitLab shard success update lifecycle from `adapter_ready` to `live_active`; on failure retain `adapter_ready` and record the non-secret failure category.

- [ ] **Step 4: Verify tests/full suite**

Run activation test module and full suite.

- [ ] **Step 5: Commit**

Commit message: `feat: activate authorized providers and preserve explicit revocation`

---

### Task 6: Reusability contract, CLI entry point, and remote acceptance

**Files:**
- Create: `experiments/zero_cost_compute_v0/unified_auth.py`
- Create: `experiments/zero_cost_compute_v0/tests/test_authorization_reuse_contract.py`
- Create: `.github/workflows/unified-authorization-v1.yml`

**Interfaces:**
- CLI:
  - `python unified_auth.py begin --provider gitlab`
  - `python unified_auth.py status --provider gitlab`
  - `python unified_auth.py ensure --provider gitlab`
  - `python unified_auth.py activate --provider gitlab`
  - `python unified_auth.py revoke --provider gitlab --explicit-user-revoke`

- [ ] **Step 1: Write failing reusability tests**

Create a second fake provider adapter implementing the same interface. The test registers it without modifying `AuthorizationCore` and proves begin/poll/ensure/revoke work through the common contract.

Also assert serialized evidence contains no keys/values matching `token`, `secret`, `password`, `refresh_token`, or any test secret literal.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest experiments.zero_cost_compute_v0.tests.test_authorization_reuse_contract -v`

- [ ] **Step 3: Implement CLI and provider registry**

Provider registration is data-driven/injected into `AuthorizationCore`. GitLab is one registered adapter; the fake second adapter proves extensibility.

- [ ] **Step 4: Add remote acceptance workflow**

Workflow runs the full test suite and writes a non-secret evidence JSON asserting:
- provider-neutral core is green;
- second-adapter contract is green;
- no secret appears in evidence;
- GitLab live activation is reported separately from code readiness;
- local formal compute percent remains 0.

The remote workflow must not perform interactive GitLab authorization and must not claim `live_active` without the local authorized run.

- [ ] **Step 5: Run remote acceptance and merge**

Create PR, verify all checks and evidence artifact, merge only when green.

- [ ] **Step 6: Local production handoff**

On the authorized Windows machine:
1. ensure `glab` is installed;
2. run the unified `begin --provider gitlab` entry;
3. user approves once on GitLab's official device authorization page;
4. run `ensure` to verify identity and bootstrap runtime trigger;
5. run `activate` for one real shard;
6. confirm registry is `AUTHORIZED` + provider lifecycle `live_active`;
7. verify closing/reopening the process does not require another user authorization;
8. verify runtime trigger repair works without user interaction;
9. retain explicit `revoke` as the only user-driven permanent stop path.

Expected completion: one user authorization persists across restarts and runtime credential repair; the second-adapter contract proves the core is reusable.
