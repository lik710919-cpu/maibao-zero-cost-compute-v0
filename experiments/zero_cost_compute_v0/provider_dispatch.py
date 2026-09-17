from collections.abc import Callable


def validate_route(route: dict) -> list[str]:
    if not isinstance(route, dict):
        raise ValueError("route must be a dictionary")
    primary = str(route.get("primary", "")).strip()
    fallbacks = route.get("fallbacks", [])
    if not primary:
        raise ValueError("route primary is required")
    if not isinstance(fallbacks, list):
        raise ValueError("route fallbacks must be a list")
    ordered = [primary, *[str(item).strip() for item in fallbacks]]
    if any(not provider_id for provider_id in ordered):
        raise ValueError("route provider IDs must be non-empty")
    if len(set(ordered)) != len(ordered):
        raise ValueError("route provider IDs must be unique")
    return ordered


def dispatch_with_failover(
    route: dict,
    execute_provider: Callable[[str], dict],
) -> dict:
    ordered = validate_route(route)
    attempts: list[dict] = []
    last_error: Exception | None = None

    for provider_id in ordered:
        try:
            result = execute_provider(provider_id)
            if not isinstance(result, dict):
                raise RuntimeError("provider executor returned a non-dictionary result")
            actual_provider = str(result.get("provider_id", provider_id)).strip()
            if actual_provider != provider_id:
                raise RuntimeError(
                    f"provider identity mismatch: routed {provider_id!r}, returned {actual_provider!r}"
                )
            attempts.append({"provider_id": provider_id, "status": "success"})
            result = dict(result)
            result["provider_id"] = provider_id
            result["dispatch_route"] = ordered
            result["dispatch_attempts"] = attempts
            result["failover_used"] = len(attempts) > 1
            return result
        except Exception as exc:
            last_error = exc
            attempts.append(
                {
                    "provider_id": provider_id,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    detail = "; ".join(
        f"{item['provider_id']}: {item.get('error', 'failed')}" for item in attempts
    )
    raise RuntimeError(f"all routed providers failed: {detail}") from last_error
