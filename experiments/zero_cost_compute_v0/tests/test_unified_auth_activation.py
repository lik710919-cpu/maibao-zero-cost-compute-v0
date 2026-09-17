import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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


class MemoryRegistry:
    def __init__(self):
        self.records = {}

    def get(self, provider_id):
        return self.records.get(provider_id)

    def put(self, record):
        self.records[record.provider_id] = record


class FakeAdapter:
    provider_id = "fake"

    def begin_authorization(self):
        from authorization_core import AuthorizationSession

        return AuthorizationSession(provider_id="fake", verification_uri="https://fake.example/authorize")

    def poll_authorization(self):
        return {"authorized": True, "account_id": "acct-1"}

    def validate_identity(self):
        return {"authorized": True, "account_id": "acct-1"}

    def inspect_scopes(self):
        return ["api"]

    def refresh_authorization(self):
        return {"authorized": True}

    def create_runtime_credentials(self, vault):
        ref = vault.put("fake/runtime", "runtime-secret")
        return {
            "runtime_credential_ref": ref,
            "runtime_credential_id": "runtime-1",
            "bound_resource": "resource-1",
        }

    def validate_runtime_credentials(self, runtime_ref, vault):
        return bool(runtime_ref) and vault.exists(runtime_ref)

    def revoke_runtime_credentials(self, runtime_ref, vault, **kwargs):
        if runtime_ref and vault.exists(runtime_ref):
            vault.delete(runtime_ref)

    def revoke_user_authorization(self):
        return None


class PendingAdapter(FakeAdapter):
    def poll_authorization(self):
        return {"authorized": False}


class UnifiedAuthorizationActivationTests(unittest.TestCase):
    def build_service(self, *, adapter=None, probe=None):
        from unified_auth import ProviderRegistration, UnifiedAuthorizationService

        vault = MemoryVault()
        registry = MemoryRegistry()
        service = UnifiedAuthorizationService(
            registrations={
                "fake": ProviderRegistration(
                    provider_id="fake",
                    adapter=adapter or FakeAdapter(),
                    authorization_required=True,
                    supports_persistent_authorization=True,
                )
            },
            vault=vault,
            registry=registry,
            activation_probes={
                "fake": probe
                or (lambda record: {
                    "verified": True,
                    "provider_id": "fake-external-compute",
                    "pipeline_id": 77,
                    "job_id": 88,
                    "local_compute_used": False,
                })
            },
        )
        return service, vault, registry

    def test_activation_runs_only_through_capability_activator_and_persists_acceptance(self):
        service, vault, registry = self.build_service()
        service.begin("fake")

        result = service.activate("fake")

        self.assertTrue(result["live_active"])
        self.assertTrue(registry.get("fake").acceptance_complete)
        self.assertTrue(service.public_status("fake")["acceptance_complete"])

    def test_activation_without_registered_probe_fails_closed(self):
        from unified_auth import ProviderRegistration, UnifiedAuthorizationService

        vault = MemoryVault()
        registry = MemoryRegistry()
        service = UnifiedAuthorizationService(
            registrations={
                "fake": ProviderRegistration(
                    provider_id="fake",
                    adapter=FakeAdapter(),
                    authorization_required=True,
                    supports_persistent_authorization=True,
                )
            },
            vault=vault,
            registry=registry,
            activation_probes={},
        )
        service.begin("fake")

        with self.assertRaises(KeyError):
            service.activate("fake")
        self.assertFalse(registry.get("fake").acceptance_complete)

    def test_onboard_authorizes_then_runs_real_activation_path(self):
        service, vault, registry = self.build_service()

        result = service.onboard("fake")

        self.assertTrue(result["live_active"])
        self.assertTrue(registry.get("fake").acceptance_complete)
        self.assertEqual(registry.get("fake").state.value, "AUTHORIZED")

    def test_onboard_never_activates_while_authorization_is_pending(self):
        called = []
        service, vault, registry = self.build_service(
            adapter=PendingAdapter(),
            probe=lambda record: called.append(record),
        )

        with self.assertRaisesRegex(RuntimeError, "authorization did not complete"):
            service.onboard("fake")

        self.assertEqual(called, [])
        self.assertEqual(registry.get("fake").state.value, "AUTHORIZING")


if __name__ == "__main__":
    unittest.main()
