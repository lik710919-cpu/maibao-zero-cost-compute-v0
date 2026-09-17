import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ResourceGrowthTests(unittest.TestCase):
    def test_seed_registry_produces_safe_next_adapter_target(self):
        import resource_growth

        candidates = resource_growth.load_candidates(ROOT / "provider_candidates.json")
        report = resource_growth.build_growth_report(candidates)

        self.assertIn("gitlab-hosted-runners", report["auto_eligible"])
        self.assertEqual(report["next_adapter_target"], "gitlab-hosted-runners")
        self.assertIn("modal-starter", report["manual_gate"])
        self.assertIn("google-cloud-run-free-tier", report["manual_gate"])
        self.assertIn("cloudflare-workers-free", report["control_only"])
        self.assertIn("kaggle-notebooks", report["research_only"])

    def test_report_fails_closed_when_no_safe_adapter_exists(self):
        import resource_growth

        unsafe = [
            {
                "provider_id": "metered",
                "zero_cash_allowance": True,
                "hard_quota_stop": False,
                "requires_billing_account": True,
                "automatic_overage_possible": True,
                "authorized_use_confirmed": True,
                "compute_class": "formal",
                "activation_mode": "api",
            }
        ]
        report = resource_growth.build_growth_report(unsafe)
        self.assertIsNone(report["next_adapter_target"])
        self.assertEqual(report["auto_eligible"], [])

    def test_cli_writes_machine_readable_evidence(self):
        import resource_growth

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "growth-report.json"
            code = resource_growth.main(
                [
                    "--registry",
                    str(ROOT / "provider_candidates.json"),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(code, 0)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["next_adapter_target"], "gitlab-hosted-runners")
            self.assertEqual(data["local_formal_compute_percent"], 0)


if __name__ == "__main__":
    unittest.main()
