import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from provider_catalog import build_catalog
from provider_model import ProviderSnapshot


def github_hosted_snapshot(
    run_id: str,
    runner_environment: str,
    repository_visibility: str,
    queue_seconds: float,
    capacity: int,
) -> ProviderSnapshot:
    authorized = bool(str(run_id).strip())
    healthy = runner_environment == "github-hosted"
    zero_cash_cost = healthy and repository_visibility == "public"
    ready = authorized and healthy and zero_cash_cost
    return ProviderSnapshot(
        provider_id="github-actions-public",
        authorized=authorized,
        healthy=healthy,
        zero_cash_cost=zero_cash_cost,
        queue_seconds=float(queue_seconds),
        capacity=int(capacity),
        evidence=f"run:{run_id}" if ready else "none",
        status="ready" if ready else "not_eligible",
    )


def current_catalog(
    run_id: str,
    runner_environment: str,
    repository_visibility: str,
    queue_seconds: float,
    capacity: int,
) -> dict:
    github = github_hosted_snapshot(
        run_id,
        runner_environment,
        repository_visibility,
        queue_seconds,
        capacity,
    )
    candidates = [
        ProviderSnapshot("netlify-free", False, True, True, 0, 0, "none", "authorization_required"),
        ProviderSnapshot("vercel-free", False, True, True, 0, 0, "none", "authorization_required"),
    ]
    catalog = build_catalog([github, *candidates])
    catalog["candidate_provider_ids"] = [provider.provider_id for provider in candidates]
    catalog["providers"] = [asdict(provider) for provider in [github, *candidates]]
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--queue-seconds", type=float, default=0.0)
    args = parser.parse_args()

    catalog = current_catalog(
        run_id=os.environ.get("GITHUB_RUN_ID", ""),
        runner_environment=os.environ.get("RUNNER_ENVIRONMENT", ""),
        repository_visibility=os.environ.get("REPO_VISIBILITY", ""),
        queue_seconds=args.queue_seconds,
        capacity=os.cpu_count() or 1,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(catalog, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
