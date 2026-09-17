import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ProviderQualificationTests(unittest.TestCase):
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
        }
        values.update(overrides)
        return provider_qualification.ProviderCandidate(**values)

    def test_hard_quota_authorized_free_compute_is_auto_eligible(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(provider_id="gitlab-hosted-runners")
        )
        self.assertEqual(result.state, "auto_eligible")

    def test_metered_overage_requires_manual_gate(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(
                provider_id="metered-cloud",
                hard_quota_stop=False,
                requires_billing_account=True,
                automatic_overage_possible=True,
            )
        )
        self.assertEqual(result.state, "manual_gate")

    def test_tiny_cpu_budget_is_control_only(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(
                provider_id="edge-worker",
                compute_class="control_only",
            )
        )
        self.assertEqual(result.state, "control_only")

    def test_missing_authorization_fails_closed_to_research_only(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(
                provider_id="unknown-provider",
                authorized_use_confirmed=False,
            )
        )
        self.assertEqual(result.state, "research_only")

    def test_no_free_allowance_fails_closed(self):
        import provider_qualification

        result = provider_qualification.qualify_candidate(
            self.candidate(
                provider_id="paid-only",
                zero_cash_allowance=False,
            )
        )
        self.assertEqual(result.state, "research_only")


if __name__ == "__main__":
    unittest.main()
