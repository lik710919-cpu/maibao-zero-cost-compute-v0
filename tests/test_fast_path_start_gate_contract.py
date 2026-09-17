from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / ".maibao" / "verify-fast-path-start-gate.py"
BINDING = ROOT / ".maibao" / "engineering-fast-path.json"


def run_verify(tmp_path: Path, receipt: dict, *, branch: str = "task/example", changed: list[str] | None = None):
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    args = [sys.executable, str(VERIFY), "--receipt", str(receipt_path), "--repository", "lik710919-cpu/maibao-zero-cost-compute-v0", "--branch", branch]
    for item in changed or []:
        args += ["--changed-path", item]
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)


def valid_receipt() -> dict:
    return {
        "schema": "MAIBAO_FAST_PATH_START_GATE_V1",
        "status": "OPEN",
        "task_id": "task-example",
        "repository": "lik710919-cpu/maibao-zero-cost-compute-v0",
        "contract_id": "MAIBAO_FAST_PATH_CROSS_REPO_BINDING_V1",
        "branch": "task/example",
        "base_commit": "0123456789abcdef0123456789abcdef01234567",
        "task_summary": "修复分片计算 bug",
        "owned_paths": ["experiments/zero_cost_compute_v0"],
        "task_type": "CODE_BUGFIX",
        "classification": {"mode": "AUTO", "reason": "CODE_BUGFIX_SIGNAL"},
        "authority": {
            "repository": "lik710919-cpu/maibao-reserve-repo",
            "ref": "feat/fast-path-machine-start-gate-20260917",
            "classifier_path": "scripts/engineering_fast_path.py",
            "cross_repo_entry_path": "scripts/engineering_fast_path_cross_repo.py",
            "catalog_path": "config/engineering_fast_paths.json"
        },
        "authority_digests": {
            "classifier_sha256": "placeholder-classifier",
            "catalog_sha256": "placeholder-catalog"
        }
    }


def test_binding_and_verifier_exist():
    assert BINDING.exists()
    assert VERIFY.exists()


def test_valid_receipt_passes(tmp_path: Path):
    result = run_verify(tmp_path, valid_receipt(), changed=["experiments/zero_cost_compute_v0/pool.py"])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["gate_status"] == "PASS"


def test_missing_receipt_fails_closed(tmp_path: Path):
    missing = tmp_path / "missing.json"
    result = subprocess.run([sys.executable, str(VERIFY), "--receipt", str(missing), "--repository", "lik710919-cpu/maibao-zero-cost-compute-v0", "--branch", "task/example"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "RECEIPT_MISSING" in result.stderr


def test_wrong_branch_fails_closed(tmp_path: Path):
    result = run_verify(tmp_path, valid_receipt(), branch="task/other")
    assert result.returncode == 2
    assert "BRANCH_MISMATCH" in result.stderr


def test_out_of_scope_change_fails_closed(tmp_path: Path):
    result = run_verify(tmp_path, valid_receipt(), changed=["docs/unrelated.md"])
    assert result.returncode == 2
    assert "PATH_OUT_OF_SCOPE" in result.stderr
