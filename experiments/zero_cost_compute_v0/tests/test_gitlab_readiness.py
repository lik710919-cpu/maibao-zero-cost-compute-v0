import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class GitLabReadinessTests(unittest.TestCase):
    def test_readiness_evidence_is_adapter_ready_but_not_falsely_live(self):
        import gitlab_readiness

        evidence = gitlab_readiness.build_readiness_evidence(
            repository_root=ROOT.parents[1],
        )
        self.assertEqual(evidence["provider_id"], "gitlab-hosted-runners")
        self.assertTrue(evidence["stage_a_adapter_ready"])
        self.assertFalse(evidence["stage_b_live_active"])
        self.assertEqual(evidence["local_formal_compute_percent"], 0)
        self.assertEqual(evidence["runner_tag"], "saas-linux-small-amd64")
        self.assertIn("authorized_gitlab_project", evidence["live_blockers"])
        self.assertIn("runtime_credentials", evidence["live_blockers"])
        self.assertIn("live_external_shard_evidence", evidence["live_blockers"])
        self.assertNotIn("secret", json.dumps(evidence).lower())
        self.assertNotIn("token", json.dumps(evidence["dispatch_preview"]).lower())

    def test_cli_writes_machine_readable_readiness_evidence(self):
        import gitlab_readiness

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "gitlab-readiness.json"
            code = gitlab_readiness.main(
                ["--repository-root", str(ROOT.parents[1]), "--output", str(output)]
            )
            self.assertEqual(code, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["stage_a_adapter_ready"])
            self.assertFalse(payload["stage_b_live_active"])


if __name__ == "__main__":
    unittest.main()
