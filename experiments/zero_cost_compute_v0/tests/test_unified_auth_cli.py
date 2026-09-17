import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class DummyVault:
    pass


class DummyRegistry:
    def get(self, provider_id):
        return None

    def put(self, record):
        return None


class DummyGitLabAdapter:
    provider_id = "gitlab"

    def __init__(self):
        self.runner = object()


class UnifiedAuthCliTests(unittest.TestCase):
    def test_gitlab_service_factory_wires_real_live_activation_probe(self):
        from gitlab_live_activation import GitLabLiveActivationProbe
        from unified_auth import build_gitlab_service

        vault = DummyVault()
        adapter = DummyGitLabAdapter()
        service = build_gitlab_service(vault=vault, registry=DummyRegistry(), gitlab=adapter)

        probe = service.activator.probes["gitlab"]
        self.assertIsInstance(probe, GitLabLiveActivationProbe)
        self.assertIs(probe.vault, vault)
        self.assertIs(probe.runner, adapter.runner)

    def test_activate_command_routes_through_unified_service(self):
        import unified_auth

        class FakeService:
            def __init__(self):
                self.calls = []

            def activate(self, provider_id):
                self.calls.append(provider_id)
                return {
                    "verified": True,
                    "provider_id": "gitlab-hosted-runners",
                    "live_active": True,
                    "local_compute_used": False,
                }

        service = FakeService()
        output = io.StringIO()
        with patch.object(unified_auth, "build_default_service", return_value=service):
            with redirect_stdout(output):
                code = unified_auth.main(["activate", "--provider", "gitlab"])

        self.assertEqual(code, 0)
        self.assertEqual(service.calls, ["gitlab"])
        self.assertIn('"live_active": true', output.getvalue().lower())

    def test_onboard_command_authorizes_then_activates_once(self):
        import unified_auth

        class FakeService:
            def __init__(self):
                self.calls = []

            def onboard(self, provider_id):
                self.calls.append(provider_id)
                return {
                    "verified": True,
                    "provider_id": "gitlab-hosted-runners",
                    "live_active": True,
                    "local_compute_used": False,
                }

        service = FakeService()
        output = io.StringIO()
        with patch.object(unified_auth, "build_default_service", return_value=service):
            with redirect_stdout(output):
                code = unified_auth.main(["onboard", "--provider", "gitlab"])

        self.assertEqual(code, 0)
        self.assertEqual(service.calls, ["gitlab"])
        self.assertIn('"live_active": true', output.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
