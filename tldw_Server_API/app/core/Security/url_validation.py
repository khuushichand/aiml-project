from fastapi import HTTPException, status

from tldw_Server_API.app.core.Security.egress import evaluate_url_policy


def assert_url_safe(url: str) -> None:
    """Validate that the given URL is safe for outbound requests (SSRF guard)."""
    result = evaluate_url_policy(url)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.reason or "URL blocked by security policy",
        )
