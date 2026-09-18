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


def wandbox_snapshot(evidence: str, status: str, compiler: str) -> ProviderSnapshot:
    real = str(evidence).startswith("real:wandbox:")
    healthy = str(status) == "0" and bool(str(compiler).strip())
    ready = real and healthy
    return ProviderSnapshot(
        provider_id="wandbox-public",
        authorized=ready,
        healthy=healthy,
        zero_cash_cost=ready,
        queue_seconds=0.0,
        capacity=1 if ready else 0,
        evidence=str(evidence) if ready else "none",
        status="ready" if ready else "not_eligible",
    )


def huggingface_snapshot(
    evidence: str,
    *,
    healthy: bool,
    free_tier_confirmed: bool,
) -> ProviderSnapshot:
    real = str(evidence).startswith("real:huggingface:")
    zero_cash_cost = real and bool(healthy) and bool(free_tier_confirmed)
    ready = real and bool(healthy) and zero_cash_cost
    return ProviderSnapshot(
        provider_id="huggingface-inference-providers",
        authorized=real,
        healthy=bool(healthy),
        zero_cash_cost=zero_cash_cost,
        queue_seconds=0.0,
        capacity=1 if ready else 0,
        evidence=str(evidence) if real else "none",
        status="ready" if ready else "not_eligible",
    )


def current_catalog(
    run_id: str,
    runner_environment: str,
    repository_visibility: str,
    queue_seconds: float,
    capacity: int,
    wandbox_result: dict | None = None,
) -> dict:
    github = github_hosted_snapshot(
        run_id,
        runner_environment,
        repository_visibility,
        queue_seconds,
        capacity,
    )
    providers = [github]
    execution_provider_ids = ["github-actions-public"] if github.status == "ready" else []

    if wandbox_result is not None:
        wandbox = wandbox_snapshot(
            str(wandbox_result.get("provider_evidence", "none")),
            str(wandbox_result.get("wandbox_status", "")),
            str(wandbox_result.get("wandbox_compiler", "")),
        )
        providers.append(wandbox)
        if (
            wandbox.status == "ready"
            and wandbox_result.get("provider_id") == "wandbox-public"
            and wandbox_result.get("runner_environment") == "wandbox-public-api"
        ):
            execution_provider_ids.append("wandbox-public")

    candidates = [
        ProviderSnapshot("netlify-free", False, False, False, 0, 0, "none", "authorization_required"),
        ProviderSnapshot("vercel-free", False, False, False, 0, 0, "none", "authorization_required"),
    ]
    providers.extend(candidates)
    catalog = build_catalog(
        providers,
        execution_provider_ids=execution_provider_ids,
    )
    catalog["candidate_provider_ids"] = [provider.provider_id for provider in candidates]
    catalog["providers"] = [asdict(provider) for provider in providers]
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--queue-seconds", type=float, default=0.0)
    parser.add_argument("--wandbox-result")
    args = parser.parse_args()

    wandbox_result = None
    if args.wandbox_result:
        wandbox_result = json.loads(Path(args.wandbox_result).read_text(encoding="utf-8"))

    catalog = current_catalog(
        run_id=os.environ.get("GITHUB_RUN_ID", ""),
        runner_environment=os.environ.get("RUNNER_ENVIRONMENT", ""),
        repository_visibility=os.environ.get("REPO_VISIBILITY", ""),
        queue_seconds=args.queue_seconds,
        capacity=os.cpu_count() or 1,
        wandbox_result=wandbox_result,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(catalog, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
