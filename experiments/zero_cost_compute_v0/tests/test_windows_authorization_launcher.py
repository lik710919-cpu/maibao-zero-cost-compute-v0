import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "tools" / "start-unified-authorization.ps1"


class WindowsAuthorizationLauncherTests(unittest.TestCase):
    def test_launcher_uses_isolated_remote_main_bootstrap_and_unified_onboard(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        lowered = text.lower()

        self.assertIn("lik710919-cpu/maibao-zero-cost-compute-v0.git", text)
        self.assertIn("authorization-bootstrap", lowered)
        self.assertIn("git fetch", lowered)
        self.assertIn("origin main", lowered)
        self.assertIn("checkout", lowered)
        self.assertIn("--detach", lowered)
        self.assertIn("origin/main", lowered)
        self.assertIn("unified_auth.py", lowered)
        self.assertIn("onboard", lowered)
        self.assertIn("--provider", lowered)
        self.assertIn("gitlab", lowered)

    def test_launcher_installs_official_glab_without_plaintext_token_path(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        lowered = text.lower()

        self.assertIn("winget", lowered)
        self.assertIn("glab.glab", lowered)
        self.assertIn("--scope", lowered)
        self.assertIn("user", lowered)
        self.assertNotIn("gitlab_token", lowered)
        self.assertNotIn("gitlab_access_token", lowered)
        self.assertNotIn("oauth_token", lowered)
        self.assertNotIn("--insecure-storage", lowered)
        self.assertNotIn("--token", lowered)

    def test_launcher_never_uses_existing_project_checkout_as_formal_baseline(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        lowered = text.lower()

        self.assertIn("$env:localappdata", lowered)
        self.assertIn("$repodir", lowered)
        self.assertNotIn("set-location $psscriptroot", lowered)
        self.assertNotIn("git pull", lowered)


if __name__ == "__main__":
    unittest.main()
