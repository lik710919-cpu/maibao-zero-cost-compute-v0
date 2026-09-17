import json
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
    def __init__(self, provider_id):
        self.provider_id = provider_id
        self.begin_calls = 0
        self.runtime_calls = 0
        self.logout_calls = 0

    def begin_authorization(self):
        from authorization_core import AuthorizationSession

        self.begin_calls += 1
        return AuthorizationSession(
            provider_id=self.provider_id,
            verification_uri=f"https://{self.provider_id}.example/authorize",
            user_code="ABCD",
        )

    def poll_authorization(self):
        return {
            "authorized": True,
            "account_id": f"acct-{self.provider_id}",
            "scopes": ["api"],
        }

    def validate_identity(self):
        return {"authorized": True, "account_id": f"acct-{self.provider_id}"}

    def inspect_scopes(self):
        return ["api"]

    def refresh_authorization(self):
        return {"authorized": True}

    def create_runtime_credentials(self, vault):
        self.runtime_calls += 1
        ref = vault.put(f"{self.provider_id}/runtime", f"secret-{self.provider_id}")
        return {
            "runtime_credential_ref": ref,
            "runtime_credential_id": f"runtime-{self.provider_id}",
            "bound_resource": f"resource-{self.provider_id}",
        }

    def validate_runtime_credentials(self, runtime_ref, vault):
        return bool(runtime_ref) and vault.exists(runtime_ref)

    def revoke_runtime_credentials(self, runtime_ref, vault):
        if runtime_ref and vault.exists(runtime_ref):
            vault.delete(runtime_ref)

    def revoke_user_authorization(self):
        self.logout_calls += 1


class AuthorizationReuseContractTests(unittest.TestCase):
    def build_service(self):
        from unified_auth import ProviderRegistration, UnifiedAuthorizationService

        vault = MemoryVault()
        registry = MemoryRegistry()
        adapters = {
            "provider-a": FakeAdapter("provider-a"),
            "provider-b": FakeAdapter("provider-b"),
        }
        registrations = {
            provider_id: ProviderRegistration(
                provider_id=provider_id,
                adapter=adapter,
                authorization_required=True,
                supports_persistent_authorization=True,
            )
            for provider_id, adapter in adapters.items()
        }
        service = UnifiedAuthorizationService(
            registrations=registrations,
            vault=vault,
            registry=registry,
        )
        return service, adapters, vault, registry

    def test_second_provider_uses_same_core_without_core_changes(self):
        service, adapters, vault, registry = self.build_service()

        first = service.begin("provider-a")
        second = service.begin("provider-b")

        self.assertEqual(first.state.value, "AUTHORIZED")
        self.assertEqual(second.state.value, "AUTHORIZED")
        self.assertEqual(adapters["provider-a"].begin_calls, 1)
        self.assertEqual(adapters["provider-b"].begin_calls, 1)
        self.assertEqual(adapters["provider-a"].runtime_calls, 1)
        self.assertEqual(adapters["provider-b"].runtime_calls, 1)

    def test_already_authorized_provider_is_reused_without_repeating_user_authorization(self):
        service, adapters, vault, registry = self.build_service()

        first = service.begin("provider-a")
        second = service.begin("provider-a")

        self.assertEqual(first.state.value, "AUTHORIZED")
        self.assertEqual(second.state.value, "AUTHORIZED")
        self.assertEqual(adapters["provider-a"].begin_calls, 1)
        self.assertEqual(adapters["provider-a"].runtime_calls, 1)

    def test_registration_fails_closed_when_persistent_auth_capability_is_unknown(self):
        from unified_auth import ProviderRegistration, UnifiedAuthorizationService

        adapter = FakeAdapter("unknown")
        with self.assertRaises(RuntimeError):
            UnifiedAuthorizationService(
                registrations={
                    "unknown": ProviderRegistration(
                        provider_id="unknown",
                        adapter=adapter,
                        authorization_required=True,
                        supports_persistent_authorization=None,
                    )
                },
                vault=MemoryVault(),
                registry=MemoryRegistry(),
            )

    def test_public_status_never_contains_secret_or_credential_reference(self):
        service, adapters, vault, registry = self.build_service()
        service.begin("provider-a")

        public = service.public_status("provider-a")
        serialized = json.dumps(public).lower()

        self.assertNotIn("secret-provider-a", serialized)
        self.assertNotIn("vault:", serialized)
        self.assertNotIn("token", serialized)
        self.assertNotIn("password", serialized)
        self.assertTrue(public["has_runtime_credential"])
        self.assertEqual(public["state"], "AUTHORIZED")

    def test_explicit_revoke_blocks_automatic_reuse_until_user_begins_again(self):
        service, adapters, vault, registry = self.build_service()
        service.begin("provider-a")
        service.revoke("provider-a", explicit_user_revoke=True)

        with self.assertRaises(RuntimeError):
            service.ensure("provider-a")

        restarted = service.begin("provider-a")
        self.assertEqual(restarted.state.value, "AUTHORIZED")
        self.assertEqual(adapters["provider-a"].begin_calls, 2)

    def test_revoke_requires_explicit_user_intent_flag(self):
        service, adapters, vault, registry = self.build_service()
        service.begin("provider-a")
        with self.assertRaises(RuntimeError):
            service.revoke("provider-a", explicit_user_revoke=False)


if __name__ == "__main__":
    unittest.main()
