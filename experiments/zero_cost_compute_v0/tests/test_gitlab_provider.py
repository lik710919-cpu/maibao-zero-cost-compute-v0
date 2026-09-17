import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class GitLabProviderTests(unittest.TestCase):
    def assignment(self):
        return {
            "index": 2,
            "range_start": 200001,
            "range_end": 300000,
            "task_kind": "sum_squares",
            "nonce": "nonce-123",
        }

    def test_budget_guard_allows_only_conservative_free_minutes(self):
        import gitlab_provider

        state = gitlab_provider.BudgetState(
            monthly_free_quota_minutes=400,
            starting_monthly_usage_minutes=100,
            adapter_usage_minutes=20,
            reserve_minutes=80,
            max_shard_minutes=5,
        )
        decision = gitlab_provider.check_dispatch_budget(state, shard_count=4)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.projected_usage_minutes, 140)
        self.assertEqual(decision.safe_limit_minutes, 320)

    def test_budget_guard_rejects_projected_use_past_reserve(self):
        import gitlab_provider

        state = gitlab_provider.BudgetState(
            monthly_free_quota_minutes=400,
            starting_monthly_usage_minutes=300,
            adapter_usage_minutes=10,
            reserve_minutes=80,
            max_shard_minutes=5,
        )
        decision = gitlab_provider.check_dispatch_budget(state, shard_count=3)
        self.assertFalse(decision.allowed)
        self.assertIn("safe free-minute budget", decision.reason)

    def test_budget_state_rejects_missing_or_invalid_safety_inputs(self):
        import gitlab_provider

        with self.assertRaises(ValueError):
            gitlab_provider.BudgetState(400, -1, 0, 80, 5)
        with self.assertRaises(ValueError):
            gitlab_provider.BudgetState(400, 0, 0, 0, 5)
        with self.assertRaises(ValueError):
            gitlab_provider.BudgetState(400, 0, 0, 80, 0)

    def test_trigger_request_uses_exact_pipeline_and_redacts_token_from_summary(self):
        import gitlab_provider

        request = gitlab_provider.build_trigger_request(
            base_url="https://gitlab.com",
            project_id="12345",
            ref="main",
            trigger_token="secret-trigger-token",
            assignment=self.assignment(),
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.url,
            "https://gitlab.com/api/v4/projects/12345/trigger/pipeline",
        )
        self.assertEqual(request.form["token"], "secret-trigger-token")
        self.assertEqual(request.form["ref"], "main")
        self.assertEqual(request.form["variables[MAIBAO_NONCE]"], "nonce-123")
        self.assertNotIn("secret-trigger-token", json.dumps(request.safe_summary()))

    def test_terminal_pipeline_status_is_fail_closed(self):
        import gitlab_provider

        self.assertEqual(gitlab_provider.pipeline_outcome("success"), "success")
        self.assertEqual(gitlab_provider.pipeline_outcome("running"), "pending")
        self.assertEqual(gitlab_provider.pipeline_outcome("pending"), "pending")
        self.assertEqual(gitlab_provider.pipeline_outcome("failed"), "failure")
        self.assertEqual(gitlab_provider.pipeline_outcome("canceled"), "failure")
        self.assertEqual(gitlab_provider.pipeline_outcome("mystery"), "failure")

    def test_result_validation_requires_provider_pipeline_job_nonce_and_bounds(self):
        import gitlab_provider

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
        validated = gitlab_provider.validate_result(
            result,
            expected_assignment=self.assignment(),
            expected_pipeline_id=77,
            expected_job_id=88,
        )
        self.assertEqual(validated["partial_sum"], 123456)

        for key, bad_value in (
            ("provider_id", "other"),
            ("pipeline_id", 76),
            ("job_id", 87),
            ("nonce", "wrong"),
            ("range_start", 1),
            ("local_compute_used", True),
        ):
            mutated = dict(result)
            mutated[key] = bad_value
            with self.assertRaises(ValueError, msg=key):
                gitlab_provider.validate_result(
                    mutated,
                    expected_assignment=self.assignment(),
                    expected_pipeline_id=77,
                    expected_job_id=88,
                )


if __name__ == "__main__":
    unittest.main()
