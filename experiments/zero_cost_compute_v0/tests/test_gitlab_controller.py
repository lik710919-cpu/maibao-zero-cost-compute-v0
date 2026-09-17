import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeSession:
    def __init__(self):
        self.posts = []
        self.gets = []
        self.pipeline_statuses = ["pending", "running", "success"]

    def post_form(self, url, form):
        self.posts.append((url, dict(form)))
        return {"id": 77, "status": "pending"}

    def get_json(self, url, read_token):
        self.gets.append((url, read_token, "json"))
        if url.endswith("/pipelines/77"):
            status = self.pipeline_statuses.pop(0)
            return {"id": 77, "status": status}
        if url.endswith("/pipelines/77/jobs"):
            return [
                {"id": 88, "name": "formal_shard", "status": "success"},
                {"id": 89, "name": "other", "status": "success"},
            ]
        raise AssertionError(url)

    def get_bytes(self, url, read_token):
        self.gets.append((url, read_token, "bytes"))
        result = {
            "provider_id": "gitlab-hosted-runners",
            "pipeline_id": 77,
            "job_id": 88,
            "chunk_index": 2,
            "range_start": 200001,
            "range_end": 300000,
            "nonce": "nonce-123",
            "partial_sum": 123456,
            "local_compute_used": False,
        }
        return json.dumps(result).encode("utf-8")


class GitLabControllerTests(unittest.TestCase):
    def assignment(self):
        return {
            "index": 2,
            "range_start": 200001,
            "range_end": 300000,
            "task_kind": "sum_squares",
            "nonce": "nonce-123",
        }

    def budget(self):
        import gitlab_provider

        return gitlab_provider.BudgetState(400, 50, 10, 80, 5)

    def test_controller_executes_exact_pipeline_job_and_artifact(self):
        import gitlab_controller

        session = FakeSession()
        result = gitlab_controller.execute_shard(
            config=gitlab_controller.GitLabConfig(
                base_url="https://gitlab.com",
                project_id="12345",
                ref="main",
            ),
            credentials=gitlab_controller.GitLabCredentials(
                trigger_token="trigger-secret",
                read_api_token="read-secret",
            ),
            budget_state=self.budget(),
            assignment=self.assignment(),
            session=session,
            sleeper=lambda _: None,
            max_polls=5,
        )

        self.assertEqual(result["pipeline_id"], 77)
        self.assertEqual(result["job_id"], 88)
        self.assertEqual(result["partial_sum"], 123456)
        self.assertEqual(len(session.posts), 1)
        self.assertTrue(any(url.endswith("/pipelines/77/jobs") for url, _, _ in session.gets))
        self.assertTrue(any("/jobs/88/artifacts/out/result.json" in url for url, _, _ in session.gets))

    def test_controller_rejects_missing_credentials_before_network(self):
        import gitlab_controller

        session = FakeSession()
        with self.assertRaises(ValueError):
            gitlab_controller.execute_shard(
                config=gitlab_controller.GitLabConfig("https://gitlab.com", "12345", "main"),
                credentials=gitlab_controller.GitLabCredentials("", "read-secret"),
                budget_state=self.budget(),
                assignment=self.assignment(),
                session=session,
                sleeper=lambda _: None,
            )
        self.assertEqual(session.posts, [])

    def test_controller_rejects_unsafe_budget_before_network(self):
        import gitlab_controller
        import gitlab_provider

        session = FakeSession()
        with self.assertRaises(RuntimeError):
            gitlab_controller.execute_shard(
                config=gitlab_controller.GitLabConfig("https://gitlab.com", "12345", "main"),
                credentials=gitlab_controller.GitLabCredentials("trigger", "read"),
                budget_state=gitlab_provider.BudgetState(400, 315, 0, 80, 10),
                assignment=self.assignment(),
                session=session,
                sleeper=lambda _: None,
            )
        self.assertEqual(session.posts, [])

    def test_controller_fails_closed_on_pipeline_failure_or_missing_job(self):
        import gitlab_controller

        class FailedSession(FakeSession):
            def __init__(self):
                super().__init__()
                self.pipeline_statuses = ["failed"]

        with self.assertRaises(RuntimeError):
            gitlab_controller.execute_shard(
                config=gitlab_controller.GitLabConfig("https://gitlab.com", "12345", "main"),
                credentials=gitlab_controller.GitLabCredentials("trigger", "read"),
                budget_state=self.budget(),
                assignment=self.assignment(),
                session=FailedSession(),
                sleeper=lambda _: None,
            )

        class MissingJobSession(FakeSession):
            def __init__(self):
                super().__init__()
                self.pipeline_statuses = ["success"]

            def get_json(self, url, read_token):
                if url.endswith("/pipelines/77"):
                    return {"id": 77, "status": self.pipeline_statuses.pop(0)}
                if url.endswith("/pipelines/77/jobs"):
                    return [{"id": 89, "name": "other", "status": "success"}]
                raise AssertionError(url)

        with self.assertRaises(RuntimeError):
            gitlab_controller.execute_shard(
                config=gitlab_controller.GitLabConfig("https://gitlab.com", "12345", "main"),
                credentials=gitlab_controller.GitLabCredentials("trigger", "read"),
                budget_state=self.budget(),
                assignment=self.assignment(),
                session=MissingJobSession(),
                sleeper=lambda _: None,
            )


if __name__ == "__main__":
    unittest.main()
