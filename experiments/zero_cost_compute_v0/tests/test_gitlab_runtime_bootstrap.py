import json
import sys
import tempfile
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


class FakeVault:
    def __init__(self):
        self.values = {}
        self.names = {}
        self.counter = 0

    def put(self, name, secret):
        self.counter += 1
        ref = f"vault:{self.counter}"
        self.values[ref] = secret
        self.names[ref] = name
        return ref

    def get(self, ref):
        return self.values[ref]

    def delete(self, ref):
        self.values.pop(ref, None)
        self.names.pop(ref, None)

    def exists(self, ref):
        return ref in self.values


class GitLabRuntimeBootstrapTests(unittest.TestCase):
    def test_existing_exact_project_is_reused_instead_of_created(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(
            FakeResult(
                stdout=json.dumps(
                    [
                        {
                            "id": 77,
                            "name": "maibao-external-compute",
                            "path": "maibao-external-compute",
                            "path_with_namespace": "mai-user/maibao-external-compute",
                            "default_branch": "main",
                        }
                    ]
                )
            )
        )
        adapter = GitLabAuthAdapter(runner=runner)

        project = adapter.ensure_project("maibao-external-compute")

        self.assertEqual(project["project_id"], "77")
        self.assertEqual(project["path_with_namespace"], "mai-user/maibao-external-compute")
        flat = [part for call, _ in runner.calls for part in call]
        self.assertNotIn("POST", flat)

    def test_missing_project_is_created_private_and_initialized(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(stdout="[]"))
        runner.queue(
            FakeResult(
                stdout=json.dumps(
                    {
                        "id": 78,
                        "name": "maibao-external-compute",
                        "path": "maibao-external-compute",
                        "path_with_namespace": "mai-user/maibao-external-compute",
                        "default_branch": "main",
                    }
                )
            )
        )
        adapter = GitLabAuthAdapter(runner=runner)

        project = adapter.ensure_project("maibao-external-compute")

        self.assertEqual(project["project_id"], "78")
        create = runner.calls[1][0]
        self.assertEqual(create[:3], ["glab", "api", "projects"])
        self.assertIn("--method", create)
        self.assertIn("POST", create)
        self.assertIn("visibility=private", create)
        self.assertIn("initialize_with_readme=true", create)

    def test_compute_bundle_creates_required_files_on_project_default_branch(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(returncode=1, stderr="404"))
        runner.queue(FakeResult(stdout="{}"))
        runner.queue(FakeResult(returncode=1, stderr="404"))
        runner.queue(FakeResult(stdout="{}"))
        adapter = GitLabAuthAdapter(runner=runner)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "experiments" / "zero_cost_compute_v0").mkdir(parents=True)
            (root / ".gitlab-ci.yml").write_text("stages: [compute]\n", encoding="utf-8")
            (root / "experiments" / "zero_cost_compute_v0" / "gitlab_worker.py").write_text(
                "print('worker')\n", encoding="utf-8"
            )
            result = adapter.ensure_compute_bundle(
                project_id="78",
                default_branch="main",
                source_root=root,
            )

        self.assertEqual(result["synced_files"], 2)
        write_calls = [call for call, _ in runner.calls if "--method" in call]
        self.assertEqual(len(write_calls), 2)
        self.assertTrue(all("POST" in call for call in write_calls))
        flattened = " ".join(" ".join(call) for call in write_calls)
        self.assertIn("branch=main", flattened)
        self.assertIn("stages: [compute]", flattened)
        self.assertIn("print('worker')", flattened)

    def test_existing_compute_bundle_files_are_updated_not_duplicated(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(stdout=json.dumps({"file_path": ".gitlab-ci.yml"})))
        runner.queue(FakeResult(stdout="{}"))
        runner.queue(FakeResult(stdout=json.dumps({"file_path": "experiments/zero_cost_compute_v0/gitlab_worker.py"})))
        runner.queue(FakeResult(stdout="{}"))
        adapter = GitLabAuthAdapter(runner=runner)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "experiments" / "zero_cost_compute_v0").mkdir(parents=True)
            (root / ".gitlab-ci.yml").write_text("stages: [compute]\n", encoding="utf-8")
            (root / "experiments" / "zero_cost_compute_v0" / "gitlab_worker.py").write_text(
                "print('worker')\n", encoding="utf-8"
            )
            adapter.ensure_compute_bundle(project_id="78", default_branch="main", source_root=root)

        write_calls = [call for call, _ in runner.calls if "--method" in call]
        self.assertEqual(len(write_calls), 2)
        self.assertTrue(all("PUT" in call for call in write_calls))

    def test_pipeline_trigger_secret_goes_directly_to_vault_and_is_not_returned(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(
            FakeResult(
                stdout=json.dumps(
                    {
                        "id": 501,
                        "description": "maibao-formal-compute",
                        "token": "glptt-super-secret-trigger",
                    }
                )
            )
        )
        vault = FakeVault()
        adapter = GitLabAuthAdapter(runner=runner)

        metadata = adapter.create_runtime_credentials(project_id="78", vault=vault)

        self.assertEqual(metadata["runtime_credential_id"], "501")
        self.assertEqual(metadata["bound_resource"], "78")
        self.assertTrue(vault.exists(metadata["runtime_credential_ref"]))
        self.assertEqual(vault.get(metadata["runtime_credential_ref"]), "glptt-super-secret-trigger")
        serialized = json.dumps(metadata)
        self.assertNotIn("glptt-super-secret-trigger", serialized)
        self.assertNotIn('"token"', serialized.lower())
        create_call = runner.calls[0][0]
        self.assertIn("projects/78/triggers", create_call)
        self.assertIn("POST", create_call)

    def test_unbound_runtime_creation_auto_bootstraps_project_and_bundle(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(stdout=json.dumps({"id": 501, "token": "trigger-secret"})))
        vault = FakeVault()
        adapter = GitLabAuthAdapter(runner=runner, project_name="maibao-external-compute")
        calls = []

        adapter.ensure_project = lambda name: {
            "project_id": "78",
            "path_with_namespace": "mai-user/maibao-external-compute",
            "default_branch": "main",
        }
        adapter.ensure_compute_bundle = lambda **kwargs: calls.append(kwargs) or {
            "project_id": "78",
            "synced_files": 2,
            "files": [".gitlab-ci.yml", "experiments/zero_cost_compute_v0/gitlab_worker.py"],
        }

        metadata = adapter.create_runtime_credentials(vault)

        self.assertEqual(metadata["bound_resource"], "78")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["project_id"], "78")
        self.assertEqual(calls[0]["default_branch"], "main")
        self.assertTrue(vault.exists(metadata["runtime_credential_ref"]))

    def test_remote_runtime_revoke_uses_nonsecret_trigger_id_and_project_id(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(stdout="{}"))
        adapter = GitLabAuthAdapter(runner=runner)

        adapter.revoke_remote_runtime_credentials(
            runtime_credential_id="501",
            bound_resource="78",
        )

        call = runner.calls[0][0]
        self.assertIn("projects/78/triggers/501", call)
        self.assertIn("DELETE", call)
        self.assertNotIn("token", " ".join(call).lower())

    def test_free_compatible_bootstrap_never_uses_project_access_token_endpoint(self):
        from gitlab_auth_adapter import GitLabAuthAdapter

        runner = FakeRunner()
        runner.queue(FakeResult(stdout=json.dumps({"id": 501, "token": "trigger-secret"})))
        vault = FakeVault()
        adapter = GitLabAuthAdapter(runner=runner)
        adapter.create_runtime_credentials(project_id="78", vault=vault)

        flattened = " ".join(part for call, _ in runner.calls for part in call)
        self.assertNotIn("access_tokens", flattened)
        self.assertNotIn("personal_access_tokens", flattened)


if __name__ == "__main__":
    unittest.main()
