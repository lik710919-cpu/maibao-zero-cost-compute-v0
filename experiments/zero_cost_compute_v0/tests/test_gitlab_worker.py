import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class GitLabWorkerTests(unittest.TestCase):
    def environment(self):
        return {
            "GITLAB_CI": "true",
            "CI_SERVER_HOST": "gitlab.com",
            "CI_PIPELINE_ID": "77",
            "CI_JOB_ID": "88",
            "CI_RUNNER_ID": "99",
            "CI_RUNNER_DESCRIPTION": "blue-1.saas-linux-small-amd64.runners-manager.gitlab.com/default",
            "CI_RUNNER_TAGS": "[saas-linux-small-amd64]",
        }

    def test_worker_builds_verified_external_result(self):
        import gitlab_worker

        result = gitlab_worker.compute_result(
            index=0,
            start=1,
            end=3,
            nonce="nonce-123",
            env=self.environment(),
        )
        self.assertEqual(result["provider_id"], "gitlab-hosted-runners")
        self.assertEqual(result["partial_sum"], 14)
        self.assertEqual(result["pipeline_id"], 77)
        self.assertEqual(result["job_id"], 88)
        self.assertEqual(result["runner_id"], 99)
        self.assertFalse(result["local_compute_used"])

    def test_worker_rejects_non_gitlab_or_non_hosted_context(self):
        import gitlab_worker

        cases = [
            {**self.environment(), "GITLAB_CI": "false"},
            {**self.environment(), "CI_SERVER_HOST": "example.com"},
            {**self.environment(), "CI_RUNNER_TAGS": "[self-hosted]"},
            {**self.environment(), "CI_PIPELINE_ID": ""},
            {**self.environment(), "CI_JOB_ID": ""},
        ]
        for env in cases:
            with self.assertRaises(RuntimeError):
                gitlab_worker.compute_result(
                    index=0,
                    start=1,
                    end=3,
                    nonce="nonce-123",
                    env=env,
                )

    def test_worker_rejects_invalid_assignment(self):
        import gitlab_worker

        with self.assertRaises(ValueError):
            gitlab_worker.compute_result(0, 0, 3, "nonce-123", self.environment())
        with self.assertRaises(ValueError):
            gitlab_worker.compute_result(0, 3, 2, "nonce-123", self.environment())
        with self.assertRaises(ValueError):
            gitlab_worker.compute_result(-1, 1, 3, "nonce-123", self.environment())
        with self.assertRaises(ValueError):
            gitlab_worker.compute_result(0, 1, 3, "", self.environment())


if __name__ == "__main__":
    unittest.main()
