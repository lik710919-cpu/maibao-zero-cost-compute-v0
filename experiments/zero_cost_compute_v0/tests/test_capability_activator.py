import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class MemoryRegistry:
    def __init__(self, record=None):
        self.record = record

    def get(self, provider_id):
        if self.record and self.record.provider_id == provider_id:
            return self.record
        return None

    def put(self, record):
        self.record = record


class MemoryVault:
    def __init__(self):
        self.values = {}

    def put(self, name, secret):
        ref = f"vault:{len(self.values) + 1}"
        self.values[ref] = secret
        return ref

    def get(self, ref):
        return self.values[ref]

    def delete(self, ref):
        self.values.pop(ref, None)

    def exists(self, ref):
        return ref in self.values


class FakeCore:
    def __init__(self, record):
        self.record = record

    def ensure_usable(self, provider_id):
        return self.record


class CapabilityActivatorTests(unittest.TestCase):
    def record(self, state=None):
        from authorization_core import AuthorizationRecord, AuthorizationState

        return AuthorizationRecord(
            provider_id="gitlab",
            state=state or AuthorizationState.AUTHORIZED,
            account_id="42",
            scopes=("gitlab_cli_oauth",),
            runtime_credential_ref="vault:1",
            runtime_credential_id="501",
            bound_resource="78",
            revoked_by_user=False,
        )

    def test_activation_requires_authorized_state(self):
        from authorization_core import AuthorizationState
        from capability_activator import CapabilityActivator

        registry = MemoryRegistry(self.record(AuthorizationState.DEGRADED))
        activator = CapabilityActivator(
            core=FakeCore(registry.record),
            registry=registry,
            probes={"gitlab": lambda record: {"verified": True, "local_compute_used": False}},
        )
        with self.assertRaises(RuntimeError):
            activator.activate("gitlab")

    def test_verified_external_probe_marks_acceptance_complete_and_live_active(self):
        from capability_activator import CapabilityActivator

        registry = MemoryRegistry(self.record())
        activator = CapabilityActivator(
            core=FakeCore(registry.record),
            registry=registry,
            probes={
                "gitlab": lambda record: {
                    "verified": True,
                    "provider_id": "gitlab-hosted-runners",
                    "pipeline_id": 77,
                    "job_id": 88,
                    "local_compute_used": False,
                }
            },
        )

        result = activator.activate("gitlab")

        self.assertTrue(result["live_active"])
        self.assertTrue(result["verified"])
        self.assertFalse(result["local_compute_used"])
        self.assertTrue(registry.record.acceptance_complete)
        self.assertIsNone(registry.record.last_error)

    def test_local_compute_evidence_can_never_activate_provider(self):
        from capability_activator import CapabilityActivator

        registry = MemoryRegistry(self.record())
        activator = CapabilityActivator(
            core=FakeCore(registry.record),
            registry=registry,
            probes={"gitlab": lambda record: {"verified": True, "local_compute_used": True}},
        )
        with self.assertRaises(RuntimeError):
            activator.activate("gitlab")
        self.assertFalse(registry.record.acceptance_complete)

    def test_probe_failure_keeps_provider_not_live_and_records_nonsecret_error(self):
        from capability_activator import CapabilityActivator

        registry = MemoryRegistry(self.record())

        def failed_probe(record):
            raise RuntimeError("pipeline failed")

        activator = CapabilityActivator(
            core=FakeCore(registry.record),
            registry=registry,
            probes={"gitlab": failed_probe},
        )
        with self.assertRaises(RuntimeError):
            activator.activate("gitlab")
        self.assertFalse(registry.record.acceptance_complete)
        self.assertEqual(registry.record.last_error, "activation_probe_failed")


class ExplicitRevocationTests(unittest.TestCase):
    def test_explicit_revoke_is_terminal_even_if_remote_cleanup_fails(self):
        from authorization_core import AuthorizationCore, AuthorizationRecord, AuthorizationState

        class FailingRevokeAdapter:
            provider_id = "fake"

            def revoke_runtime_credentials(self, runtime_ref, vault, **kwargs):
                raise RuntimeError("remote provider unavailable")

            def revoke_user_authorization(self):
                raise RuntimeError("remote logout unavailable")

        vault = MemoryVault()
        runtime_ref = vault.put("fake/runtime", "runtime-secret")
        user_ref = vault.put("fake/user", "user-secret")
        registry = MemoryRegistry(
            AuthorizationRecord(
                provider_id="fake",
                state=AuthorizationState.AUTHORIZED,
                user_credential_ref=user_ref,
                runtime_credential_ref=runtime_ref,
                runtime_credential_id="runtime-9",
                bound_resource="resource-4",
            )
        )
        core = AuthorizationCore(adapters={"fake": FailingRevokeAdapter()}, vault=vault, registry=registry)

        revoked = core.revoke("fake")

        self.assertEqual(revoked.state, AuthorizationState.REVOKED_BY_USER)
        self.assertTrue(revoked.revoked_by_user)
        self.assertFalse(vault.exists(runtime_ref))
        self.assertFalse(vault.exists(user_ref))
        self.assertEqual(revoked.last_error, "remote_revocation_incomplete")
        with self.assertRaises(RuntimeError):
            core.ensure_usable("fake")

    def test_explicit_revoke_attempts_remote_runtime_cleanup_using_only_nonsecret_ids(self):
        from authorization_core import AuthorizationCore, AuthorizationRecord, AuthorizationState

        class RevokeAdapter:
            provider_id = "fake"

            def __init__(self):
                self.remote = []

            def revoke_runtime_credentials(self, runtime_ref, vault):
                return None

            def revoke_remote_runtime_credentials(self, *, runtime_credential_id, bound_resource):
                self.remote.append((runtime_credential_id, bound_resource))

            def revoke_user_authorization(self):
                return None

        adapter = RevokeAdapter()
        vault = MemoryVault()
        runtime_ref = vault.put("fake/runtime", "runtime-secret")
        registry = MemoryRegistry(
            AuthorizationRecord(
                provider_id="fake",
                state=AuthorizationState.AUTHORIZED,
                runtime_credential_ref=runtime_ref,
                runtime_credential_id="501",
                bound_resource="78",
            )
        )
        core = AuthorizationCore(adapters={"fake": adapter}, vault=vault, registry=registry)

        core.revoke("fake")

        self.assertEqual(adapter.remote, [("501", "78")])
        self.assertFalse(vault.exists(runtime_ref))

    def test_runtime_repair_persists_provider_runtime_metadata(self):
        from authorization_core import AuthorizationCore, AuthorizationRecord, AuthorizationState

        class RepairAdapter:
            provider_id = "fake"

            def validate_identity(self):
                return {"authorized": True}

            def refresh_authorization(self):
                return {"authorized": True}

            def validate_runtime_credentials(self, runtime_ref, vault):
                return False

            def create_runtime_credentials(self, vault):
                ref = vault.put("fake/runtime", "new-runtime-secret")
                return {
                    "runtime_credential_ref": ref,
                    "runtime_credential_id": "trigger-501",
                    "bound_resource": "project-78",
                }

        vault = MemoryVault()
        registry = MemoryRegistry(
            AuthorizationRecord(provider_id="fake", state=AuthorizationState.AUTHORIZED)
        )
        core = AuthorizationCore(adapters={"fake": RepairAdapter()}, vault=vault, registry=registry)

        repaired = core.ensure_usable("fake")

        self.assertEqual(repaired.state, AuthorizationState.AUTHORIZED)
        self.assertEqual(repaired.runtime_credential_id, "trigger-501")
        self.assertEqual(repaired.bound_resource, "project-78")


if __name__ == "__main__":
    unittest.main()
