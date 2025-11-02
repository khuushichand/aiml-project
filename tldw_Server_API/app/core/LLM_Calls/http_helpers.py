from typing import Iterable, Iterator, Optional, Dict, Any
import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session_with_retries(
    total: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: Optional[Iterable[int]] = None,
    allowed_methods: Optional[Iterable[str]] = None,
) -> Session:
    """Create a requests.Session configured with retry strategy on both http/https.

    Args:
        total: Total retry attempts
        backoff_factor: Backoff multiplier
        status_forcelist: HTTP statuses that trigger a retry
        allowed_methods: Methods to retry (e.g., ["POST"]) for modern urllib3
    """
    status_forcelist = list(status_forcelist or [429, 500, 502, 503, 504])
    allowed_methods = list(allowed_methods or ["POST"])  # retry POST for LLM APIs
    retry = Retry(total=total, backoff_factor=backoff_factor, status_forcelist=status_forcelist, allowed_methods=allowed_methods)
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
