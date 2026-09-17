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
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []

    def run(self, args, *, capture=True):
        self.calls.append((list(args), capture))
        if not self.results:
            raise AssertionError(f"unexpected command: {args}")
        return self.results.pop(0)


class FakeVault:
    def __init__(self, values):
        self.values = dict(values)

    def get(self, ref):
        return self.values[ref]


class GitLabLiveActivationTests(unittest.TestCase):
    def record(self):
        from authorization_core import AuthorizationRecord, AuthorizationState

        return AuthorizationRecord(
            provider_id="gitlab",
            state=AuthorizationState.AUTHORIZED,
            account_id="42",
            runtime_credential_ref="vault:trigger",
            runtime_credential_id="501",
            bound_resource="78",
        )

    def test_probe_reads_namespace_usage_through_glab_without_exporting_oauth_token(self):
        from gitlab_live_activation import GitLabLiveActivationProbe

        runner = FakeRunner(
            [
                FakeResult(stdout=json.dumps({"id": 78, "namespace": {"id": 9, "full_path": "mai-user"}, "default_branch": "main"})),
                FakeResult(stdout=json.dumps({"id": 9, "full_path": "mai-user", "plan": "free", "ci_minutes_usage": {"monthly_minutes_used": 12}})),
            ]
        )
        probe = GitLabLiveActivationProbe(
            vault=FakeVault({"vault:trigger": "trigger-secret"}),
            runner=runner,
            execute=lambda **kwargs: {
                "provider_id": "gitlab-hosted-runners",
                "pipeline_id": 77,
                "job_id": 88,
                "chunk_index": 0,
                "range_start": 1,
                "range_end": 1000,
                "nonce": "activation-probe",
                "partial_sum": 333833500,
                "local_compute_used": False,
            },
        )

        evidence = probe(self.record())

        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["namespace_monthly_minutes_used"], 12)
        flattened = " ".join(part for call, _ in runner.calls for part in call)
        self.assertIn("glab api", flattened)
        self.assertNotIn("auth token", flattened.lower())
        self.assertNotIn("show-token", flattened.lower())
        self.assertNotIn("trigger-secret", json.dumps(evidence))

    def test_probe_fails_closed_when_compute_usage_is_not_visible(self):
        from gitlab_live_activation import GitLabLiveActivationProbe

        runner = FakeRunner(
            [
                FakeResult(stdout=json.dumps({"id": 78, "namespace": {"id": 9}, "default_branch": "main"})),
                FakeResult(stdout=json.dumps({"id": 9, "plan": "free"})),
            ]
        )
        probe = GitLabLiveActivationProbe(
            vault=FakeVault({"vault:trigger": "trigger-secret"}),
            runner=runner,
            execute=lambda **kwargs: self.fail("formal dispatch must not occur without visible usage"),
        )

        with self.assertRaisesRegex(RuntimeError, "compute usage"):
            probe(self.record())

    def test_probe_rejects_mathematically_wrong_external_result(self):
        from gitlab_live_activation import GitLabLiveActivationProbe

        runner = FakeRunner(
            [
                FakeResult(stdout=json.dumps({"id": 78, "namespace": {"id": 9}, "default_branch": "main"})),
                FakeResult(stdout=json.dumps({"id": 9, "plan": "free", "ci_minutes_usage": {"monthly_minutes_used": 0}})),
            ]
        )
        probe = GitLabLiveActivationProbe(
            vault=FakeVault({"vault:trigger": "trigger-secret"}),
            runner=runner,
            execute=lambda **kwargs: {
                "provider_id": "gitlab-hosted-runners",
                "pipeline_id": 77,
                "job_id": 88,
                "chunk_index": 0,
                "range_start": 1,
                "range_end": 1000,
                "nonce": "activation-probe",
                "partial_sum": 1,
                "local_compute_used": False,
            },
        )

        with self.assertRaisesRegex(RuntimeError, "sum verification"):
            probe(self.record())


if __name__ == "__main__":
    unittest.main()
