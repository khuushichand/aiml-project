"""Helpers to construct a real requests.Session with retry for streaming paths.

This module must NOT import the central shim from LLM_API_Calls to avoid
recursion. It returns a plain requests.Session configured with urllib3 Retry.
"""

from typing import Iterable, Optional


def create_session_with_retries(
    total: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: Optional[Iterable[int]] = None,
    allowed_methods: Optional[Iterable[str]] = None,
):
    import requests
    try:
        # urllib3 Retry available via requests' vendored urllib3
        from urllib3.util.retry import Retry  # type: ignore
    except Exception:  # pragma: no cover
        # Fallback minimal session without retries
        session_cls = getattr(requests, "Session")
        return session_cls()

    from requests.adapters import HTTPAdapter

    status_list = list(status_forcelist or [429, 500, 502, 503, 504])
    methods_list = list(allowed_methods or ["POST"])

    retry = Retry(
        total=max(0, int(total)),
        backoff_factor=float(backoff_factor),
        status_forcelist=status_list,
        allowed_methods=set(m.upper() for m in methods_list),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session_cls = getattr(requests, "Session")
    session = session_cls()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
