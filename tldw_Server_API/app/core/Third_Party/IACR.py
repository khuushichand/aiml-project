"""IACR conference metadata adapter.

Fetches metadata for a given venue and year.
Example: https://www.iacr.org/cryptodb/data/api/conf.php?year=2017&venue=crypto
"""
from __future__ import annotations

from typing import Optional, Tuple, Dict, Any
import requests
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tldw_Server_API.app.core.http_client import create_client


BASE_URL = "https://www.iacr.org/cryptodb/data/api/conf.php"


def _mk_session():
    try:
        return create_client(timeout=20)
    except Exception:
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        s = requests.Session()
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s


def fetch_conference(venue: str, year: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Returns parsed JSON for the requested conference."""
    try:
        session = _mk_session()
        params = {"venue": venue, "year": str(year)}
        r = session.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to IACR API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"IACR API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to IACR API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"IACR API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"IACR API Request Error: {str(e)}"
        return None, f"IACR error: {str(e)}"


def fetch_conference_raw(venue: str, year: int) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Returns raw bytes and media type for the requested conference."""
    try:
        session = _mk_session()
        params = {"venue": venue, "year": str(year)}
        r = session.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        ct = r.headers.get("content-type") or "application/json"
        return r.content, ct.split(";")[0], None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to IACR API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"IACR API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to IACR API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"IACR API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"IACR API Request Error: {str(e)}"
        return None, None, f"IACR error: {str(e)}"
