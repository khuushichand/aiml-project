from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter


def test_rate_limiter_reset_rate_limit_shim_removed() -> None:
    assert not hasattr(RateLimiter, "reset_rate_limit")  # nosec B101
