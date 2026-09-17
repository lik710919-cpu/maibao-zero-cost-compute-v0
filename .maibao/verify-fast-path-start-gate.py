from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BINDING_PATH = ROOT / ".maibao" / "engineering-fast-path.json"


def read_json(path: Path, missing_code: str) -> dict:
    if not path.exists():
        raise ValueError(missing_code)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"FAST_PATH_START_GATE_JSON_INVALID:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"FAST_PATH_START_GATE_JSON_INVALID:{path}")
    return payload


def normalize(value: str) -> str:
    text = str(value).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def in_scope(changed: str, owned_paths: list[str]) -> bool:
    candidate = normalize(changed)
    if candidate.startswith(".maibao/fast-path-"):
        return True
    for raw in owned_paths:
        scope = normalize(raw)
        if scope and (candidate == scope or candidate.startswith(scope.rstrip("/") + "/")):
            return True
    return False


def verify(receipt_path: Path, repository: str, branch: str, changed_paths: list[str]) -> dict:
    binding = read_json(BINDING_PATH, "FAST_PATH_START_GATE_BINDING_MISSING")
    receipt = read_json(receipt_path, "FAST_PATH_START_GATE_RECEIPT_MISSING")

    if binding.get("classification_required") is not True or binding.get("start_gate_required") is not True:
        raise ValueError("FAST_PATH_START_GATE_BINDING_NOT_REQUIRED")
    if binding.get("fallback") != "FAIL_CLOSED" or binding.get("remote_gate") != "FAIL_CLOSED":
        raise ValueError("FAST_PATH_START_GATE_BINDING_NOT_FAIL_CLOSED")
    if binding.get("hard_authority_boundary_overridable") is not False:
        raise ValueError("FAST_PATH_START_GATE_BOUNDARY_INVALID")

    if receipt.get("schema") != binding.get("receipt_schema"):
        raise ValueError("FAST_PATH_START_GATE_SCHEMA_MISMATCH")
    if receipt.get("status") != "OPEN":
        raise ValueError("FAST_PATH_START_GATE_NOT_OPEN")
    if receipt.get("repository") != repository or binding.get("repository") != repository:
        raise ValueError("FAST_PATH_START_GATE_REPO_MISMATCH")
    if receipt.get("contract_id") != binding.get("contract_id"):
        raise ValueError("FAST_PATH_START_GATE_CONTRACT_MISMATCH")
    if receipt.get("branch") != branch:
        raise ValueError("FAST_PATH_START_GATE_BRANCH_MISMATCH")

    authority = receipt.get("authority") or {}
    if authority.get("repository") != binding.get("authority_repository"):
        raise ValueError("FAST_PATH_START_GATE_AUTHORITY_MISMATCH")
    if authority.get("ref") != binding.get("authority_ref"):
        raise ValueError("FAST_PATH_START_GATE_AUTHORITY_REF_MISMATCH")
    if authority.get("cross_repo_entry_path") != binding.get("authority_entry"):
        raise ValueError("FAST_PATH_START_GATE_AUTHORITY_ENTRY_MISMATCH")

    authority_blobs = receipt.get("authority_blobs") or {}
    expected_blobs = {
        "classifier_blob_sha": binding.get("authority_classifier_blob_sha"),
        "catalog_blob_sha": binding.get("authority_catalog_blob_sha"),
    }
    if authority_blobs != expected_blobs:
        raise ValueError("FAST_PATH_START_GATE_AUTHORITY_BLOB_MISMATCH")

    if not receipt.get("task_id") or not receipt.get("base_commit") or not receipt.get("task_summary"):
        raise ValueError("FAST_PATH_START_GATE_RECEIPT_INCOMPLETE")
    if receipt.get("task_type") not in {"CODE_BUGFIX", "CONFIG_CONTRACT", "DOCUMENT_ONLY", "PROVIDER_INTERNAL", "LINE_REPAIR", "NON_FAST_PATH"}:
        raise ValueError("FAST_PATH_START_GATE_TASK_TYPE_INVALID")

    is_catch_up = receipt.get("catch_up_audit") is True
    if is_catch_up:
        reason = str(receipt.get("catch_up_reason", "")).strip()
        if not reason:
            raise ValueError("FAST_PATH_START_GATE_CATCH_UP_REASON_REQUIRED")
    else:
        digests = receipt.get("authority_digests") or {}
        if not digests.get("classifier_sha256") or not digests.get("catalog_sha256"):
            raise ValueError("FAST_PATH_START_GATE_AUTHORITY_DIGEST_MISSING")

    owned_paths = [normalize(item) for item in receipt.get("owned_paths", []) if normalize(item)]
    for changed in changed_paths:
        if not in_scope(changed, owned_paths):
            raise ValueError(f"FAST_PATH_START_GATE_PATH_OUT_OF_SCOPE:{normalize(changed)}")

    return {
        "gate_status": "PASS",
        "task_id": receipt["task_id"],
        "repository": repository,
        "branch": branch,
        "task_type": receipt["task_type"],
        "authority_ref": authority["ref"],
        "authority_blobs": authority_blobs,
        "catch_up_audit": is_catch_up,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a MaiBao Fast Path start-gate receipt without duplicating classification logic")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--changed-path", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        payload = verify(Path(args.receipt), args.repository, args.branch, list(args.changed_path))
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
