import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class AuthorizationStorageTests(unittest.TestCase):
    def test_registry_never_serializes_secret_values(self):
        from authorization_core import AuthorizationRecord, AuthorizationState
        from authorization_storage import JsonAuthorizationRegistry, MemoryCredentialVault

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "authorization-registry.json"
            vault = MemoryCredentialVault()
            secret_ref = vault.put("fake/user", "super-secret-value")
            runtime_ref = vault.put("fake/runtime", "runtime-secret-value")
            registry = JsonAuthorizationRegistry(path)
            registry.put(
                AuthorizationRecord(
                    provider_id="fake",
                    state=AuthorizationState.AUTHORIZED,
                    account_id="acct-1",
                    scopes=("api",),
                    user_credential_ref=secret_ref,
                    runtime_credential_ref=runtime_ref,
                    revoked_by_user=False,
                )
            )
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("super-secret-value", text)
            self.assertNotIn("runtime-secret-value", text)
            self.assertIn(secret_ref, text)
            self.assertIn(runtime_ref, text)

    def test_vault_reference_is_opaque_and_round_trips(self):
        from authorization_storage import MemoryCredentialVault

        vault = MemoryCredentialVault()
        ref = vault.put("fake/runtime", "runtime-secret-value")
        self.assertNotIn("runtime-secret-value", ref)
        self.assertTrue(ref.startswith("memvault:"))
        self.assertEqual(vault.get(ref), "runtime-secret-value")
        self.assertTrue(vault.exists(ref))
        vault.delete(ref)
        self.assertFalse(vault.exists(ref))

    def test_registry_round_trips_authorization_state(self):
        from authorization_core import AuthorizationRecord, AuthorizationState
        from authorization_storage import JsonAuthorizationRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "authorization-registry.json"
            registry = JsonAuthorizationRegistry(path)
            original = AuthorizationRecord(
                provider_id="fake",
                state=AuthorizationState.DEGRADED,
                account_id="acct-1",
                scopes=("read_api", "api"),
                user_credential_ref="opaque:user",
                runtime_credential_ref="opaque:runtime",
                revoked_by_user=False,
                bound_resource="project-7",
                acceptance_complete=False,
                last_error="temporary_failure",
            )
            registry.put(original)
            reloaded = JsonAuthorizationRegistry(path).get("fake")
            self.assertEqual(reloaded, original)

    def test_windows_vault_can_be_constructed_cross_platform_without_touching_win32(self):
        from authorization_storage import WindowsCredentialVault

        vault = WindowsCredentialVault(prefix="maibao-auth-test")
        self.assertEqual(vault.prefix, "maibao-auth-test")


if __name__ == "__main__":
    unittest.main()
