import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.results = []

    def queue(self, result):
        self.results.append(result)

    def run(self, args, *, capture=True):
        self.calls.append((list(args), capture))
        if self.results:
            return self.results.pop(0)
        return FakeResult()


class GitLabAuthAdapterTests(unittest.TestCase):
    def test_begin_authorization_uses_official_device_flow(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        adapter = GitLabAuthAdapter(runner=runner)
        session = adapter.begin_authorization()

        self.assertEqual(
            runner.calls[0],
            (["glab", "auth", "login", "--hostname", "gitlab.com", "--device"], False),
        )
        self.assertEqual(session.provider_id, "gitlab")
        self.assertEqual(session.verification_uri, "https://gitlab.com/oauth/device")

    def test_validate_identity_uses_authenticated_glab_api_and_returns_no_secret(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(stdout=json.dumps({"id": 42, "username": "mai-user", "name": "Mai"})))
        adapter = GitLabAuthAdapter(runner=runner)

        identity = adapter.validate_identity()

        self.assertEqual(
            runner.calls[0],
            (["glab", "api", "user", "--hostname", "gitlab.com", "--output", "json"], True),
        )
        self.assertTrue(identity["authorized"])
        self.assertEqual(identity["account_id"], "42")
        self.assertEqual(identity["username"], "mai-user")
        serialized = json.dumps(identity).lower()
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("refresh_token", serialized)
        self.assertNotIn("password", serialized)

    def test_refresh_authorization_prefers_noninteractive_identity_check(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(stdout=json.dumps({"id": 42, "username": "mai-user"})))
        adapter = GitLabAuthAdapter(runner=runner)

        result = adapter.refresh_authorization()

        self.assertTrue(result["authorized"])
        self.assertFalse(result.get("reauth_required", False))
        self.assertEqual(runner.calls[0][0][:3], ["glab", "api", "user"])

    def test_refresh_authorization_requests_reauth_only_when_stored_auth_cannot_work(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(returncode=1, stderr="authentication failed"))
        adapter = GitLabAuthAdapter(runner=runner)

        result = adapter.refresh_authorization()

        self.assertTrue(result["reauth_required"])
        self.assertFalse(result.get("authorized", False))

    def test_adapter_never_uses_show_token(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(stdout=json.dumps({"id": 42, "username": "mai-user"})))
        adapter = GitLabAuthAdapter(runner=runner)
        adapter.validate_identity()

        flat = " ".join(runner.calls[0][0])
        self.assertNotIn("--show-token", flat)


if __name__ == "__main__":
    unittest.main()
