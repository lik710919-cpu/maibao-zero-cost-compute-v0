import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class PolicyCapacityGrowthTests(unittest.TestCase):
    def candidate(self, **overrides):
        import provider_qualification

        values = {
            "provider_id": "candidate",
            "zero_cash_allowance": True,
            "hard_quota_stop": True,
            "requires_billing_account": False,
            "automatic_overage_possible": False,
            "authorized_use_confirmed": True,
            "compute_class": "formal",
            "activation_mode": "api",
            "terms_scope": "general_compute",
            "terms_scope_confirmed": True,
            "external_authorization_required": False,
            "formal_pool_eligible": True,
        }
        values.update(overrides)
        return provider_qualification.ProviderCandidate(**values)

    def test_large_unresolved_quota_stays_behind_policy_gate(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(
                provider_id="circleci-open-source",
                hard_quota_stop=False,
                terms_scope="project_ci_only",
                terms_scope_confirmed=False,
                formal_pool_eligible=False,
            )
        )
        self.assertEqual(result.state, "policy_gate")

    def test_developer_environment_is_not_general_formal_pool_capacity(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(
                provider_id="github-codespaces-personal",
                terms_scope="developer_environment",
                terms_scope_confirmed=True,
                formal_pool_eligible=False,
            )
        )
        self.assertEqual(result.state, "developer_environment")

    def test_billing_backed_free_grant_remains_manual_gate(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(
                provider_id="azure-devops-private-free",
                requires_billing_account=True,
                automatic_overage_possible=True,
                external_authorization_required=True,
            )
        )
        self.assertEqual(result.state, "manual_gate")

    def test_external_authorization_requirement_prevents_auto_eligibility(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(
                provider_id="needs-account-approval",
                external_authorization_required=True,
            )
        )
        self.assertEqual(result.state, "manual_gate")

    def test_general_compute_policy_safe_candidate_can_remain_auto_eligible(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(self.candidate())
        self.assertEqual(result.state, "auto_eligible")


if __name__ == "__main__":
    unittest.main()
