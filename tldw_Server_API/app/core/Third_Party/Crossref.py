"""Crossref client for DOI lookups and venue-constrained searches.

No API key required. Implements basic search and DOI lookup with retries and
standardized return signatures expected by the API layer.
"""
from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any
import requests
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tldw_Server_API.app.core.http_client import create_client


BASE_URL = "https://api.crossref.org"


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


def _join_authors(authors: Any) -> Optional[str]:
    try:
        names = []
        for a in authors or []:
            given = (a or {}).get("given")
            family = (a or {}).get("family")
            if family and given:
                names.append(f"{given} {family}")
            elif family:
                names.append(family)
            elif given:
                names.append(given)
        return ", ".join(names) if names else None
    except Exception:
        return None


def _first(lst: Any) -> Optional[str]:
    if isinstance(lst, list) and lst:
        return str(lst[0])
    return None


def _date_from_message(msg: Dict[str, Any]) -> Optional[str]:
    for key in ("published-online", "published-print", "issued"):
        parts = (((msg.get(key) or {}).get("date-parts") or []) or [])
        if parts and isinstance(parts[0], list) and parts[0]:
            arr = parts[0]
            # YYYY[-MM[-DD]]
            if len(arr) >= 3:
                return f"{arr[0]:04d}-{arr[1]:02d}-{arr[2]:02d}"
            if len(arr) == 2:
                return f"{arr[0]:04d}-{arr[1]:02d}-01"
            if len(arr) == 1:
                return f"{arr[0]:04d}"
    return None


def _pdf_link(msg: Dict[str, Any]) -> Optional[str]:
    for lk in (msg.get("link") or []):
        if (lk.get("content-type") or "").lower() == "application/pdf":
            if lk.get("URL"):
                return lk.get("URL")
    return None


def _normalize_item(msg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": msg.get("DOI"),
        "title": _first(msg.get("title")) or "",
        "authors": _join_authors(msg.get("author")),
        "journal": _first(msg.get("container-title")),
        "pub_date": _date_from_message(msg),
        "abstract": None,  # Crossref sometimes includes JATS abstracts; skip for now
        "doi": msg.get("DOI"),
        "url": msg.get("URL"),
        "pdf_url": _pdf_link(msg),
        "provider": "crossref",
    }


def search_crossref(
    q: Optional[str],
    offset: int,
    limit: int,
    filter_venue: Optional[str] = None,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
) -> Tuple[Optional[List[Dict]], int, Optional[str]]:
    try:
        session = _mk_session()
        url = f"{BASE_URL}/works"
        params: Dict[str, Any] = {
            "rows": limit,
            "offset": offset,
        }
        if q:
            params["query"] = q
        # Use filter for dates; use query.container-title for venue
        filters = []
        if from_year:
            filters.append(f"from-pub-date:{from_year}-01-01")
        if to_year:
            filters.append(f"to-pub-date:{to_year}-12-31")
        if filters:
            params["filter"] = ",".join(filters)
        if filter_venue:
            params["query.container-title"] = filter_venue

        r = session.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        message = data.get("message") or {}
        items_raw = message.get("items") or []
        total = int(message.get("total-results") or 0)
        items = [_normalize_item(it) for it in items_raw]
        return items, total, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to Crossref API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"Crossref API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to Crossref API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"Crossref API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"Crossref API Request Error: {str(e)}"
        return None, 0, f"Crossref error: {str(e)}"


def get_crossref_by_doi(doi: str) -> Tuple[Optional[Dict], Optional[str]]:
    try:
        session = _mk_session()
        doi_clean = doi.strip()
        url = f"{BASE_URL}/works/{doi_clean}"
        r = session.get(url, timeout=20)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json() or {}
        msg = (data.get("message") or {})
        return _normalize_item(msg), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to Crossref API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"Crossref API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to Crossref API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"Crossref API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"Crossref API Request Error: {str(e)}"
        return None, f"Crossref error: {str(e)}"
