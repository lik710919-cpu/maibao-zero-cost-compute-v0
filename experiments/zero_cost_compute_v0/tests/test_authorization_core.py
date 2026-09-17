import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeVault:
    def __init__(self):
        self._values = {}
        self._counter = 0

    def put(self, name, secret):
        self._counter += 1
        ref = f"fake:{self._counter}"
        self._values[ref] = secret
        return ref

    def get(self, ref):
        return self._values[ref]

    def delete(self, ref):
        self._values.pop(ref, None)

    def exists(self, ref):
        return ref in self._values


class FakeRegistry:
    def __init__(self, record=None):
        self.record = record

    def get(self, provider_id):
        if self.record and self.record.provider_id == provider_id:
            return self.record
        return None

    def put(self, record):
        self.record = record


class FakeAdapter:
    provider_id = "fake"

    def __init__(self, runtime_valid=True, refreshable=True, provider_error=False):
        self.runtime_valid = runtime_valid
        self.refreshable = refreshable
        self.provider_error = provider_error
        self.refresh_calls = 0
        self.revoke_calls = 0

    def begin_authorization(self):
        from authorization_core import AuthorizationSession
        return AuthorizationSession(provider_id="fake", verification_uri="https://example.test/auth", user_code="ABCD")

    def poll_authorization(self):
        return {"authorized": True, "account_id": "acct-1", "scopes": ["api"]}

    def validate_identity(self):
        if self.provider_error:
            raise RuntimeError("temporary provider error")
        return {"authorized": True, "account_id": "acct-1", "scopes": ["api"]}

    def inspect_scopes(self):
        return ["api"]

    def refresh_authorization(self):
        self.refresh_calls += 1
        if not self.refreshable:
            return {"reauth_required": True}
        return {"authorized": True}

    def create_runtime_credentials(self, vault):
        ref = vault.put("fake/runtime", "runtime-secret")
        self.runtime_valid = True
        return {"runtime_credential_ref": ref}

    def validate_runtime_credentials(self, runtime_ref, vault):
        return self.runtime_valid and bool(runtime_ref) and vault.exists(runtime_ref)

    def revoke_runtime_credentials(self, runtime_ref, vault):
        self.revoke_calls += 1
        if runtime_ref:
            vault.delete(runtime_ref)

    def revoke_user_authorization(self):
        self.revoke_calls += 1


def build_core(*, runtime_valid=True, refreshable=True, provider_error=False):
    from authorization_core import AuthorizationCore, AuthorizationRecord, AuthorizationState

    vault = FakeVault()
    runtime_ref = vault.put("fake/runtime", "runtime-secret")
    record = AuthorizationRecord(
        provider_id="fake",
        state=AuthorizationState.AUTHORIZED,
        account_id="acct-1",
        scopes=("api",),
        user_credential_ref="fake:user",
        runtime_credential_ref=runtime_ref,
        revoked_by_user=False,
    )
    registry = FakeRegistry(record)
    adapter = FakeAdapter(
        runtime_valid=runtime_valid,
        refreshable=refreshable,
        provider_error=provider_error,
    )
    core = AuthorizationCore(adapters={"fake": adapter}, vault=vault, registry=registry)
    return core, adapter, vault, registry


class AuthorizationCoreTests(unittest.TestCase):
    def test_expired_runtime_credential_repairs_without_losing_user_authorization(self):
        from authorization_core import AuthorizationState

        core, adapter, vault, registry = build_core(runtime_valid=False, refreshable=True)
        record = core.ensure_usable("fake")
        self.assertEqual(record.state, AuthorizationState.AUTHORIZED)
        self.assertTrue(record.runtime_credential_ref)
        self.assertEqual(adapter.refresh_calls, 1)

    def test_transient_failure_degrades_but_does_not_revoke(self):
        from authorization_core import AuthorizationState

        core, adapter, vault, registry = build_core(provider_error=True)
        record = core.ensure_usable("fake")
        self.assertEqual(record.state, AuthorizationState.DEGRADED)
        self.assertFalse(record.revoked_by_user)

    def test_nonrefreshable_user_authorization_requests_reauth_without_revoking(self):
        from authorization_core import AuthorizationState

        core, adapter, vault, registry = build_core(runtime_valid=False, refreshable=False)
        record = core.ensure_usable("fake")
        self.assertEqual(record.state, AuthorizationState.REAUTH_REQUIRED)
        self.assertFalse(record.revoked_by_user)

    def test_explicit_user_revoke_is_terminal_until_new_begin(self):
        from authorization_core import AuthorizationState

        core, adapter, vault, registry = build_core()
        revoked = core.revoke("fake")
        self.assertEqual(revoked.state, AuthorizationState.REVOKED_BY_USER)
        self.assertTrue(revoked.revoked_by_user)
        with self.assertRaises(RuntimeError):
            core.ensure_usable("fake")


if __name__ == "__main__":
    unittest.main()
