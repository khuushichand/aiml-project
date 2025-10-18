"""Elsevier Scopus adapter.

Uses API key when present. Implements basic search and DOI lookup with retries
and normalization. Some features may require institutional entitlements.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple, List, Dict, Any
import requests
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tldw_Server_API.app.core.http_client import create_client


def _missing_key_error() -> str:
    return "Elsevier API key not configured. Set ELSEVIER_API_KEY to enable Scopus provider."


BASE_URL = "https://api.elsevier.com/content/search/scopus"


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


def _headers() -> Dict[str, str]:
    h = {
        "X-ELS-APIKey": os.getenv("ELSEVIER_API_KEY", ""),
        "Accept": "application/json",
    }
    inst = os.getenv("ELSEVIER_INST_TOKEN")
    if inst:
        h["X-ELS-Insttoken"] = inst
    return h


def _join_authors(entry: Dict[str, Any]) -> Optional[str]:
    # Scopus search returns 'dc:creator' (first author) and 'author' array in detailed endpoints.
    # Here we best-effort use 'dc:creator'.
    name = entry.get("dc:creator")
    return name if name else None


def _pdf_url(entry: Dict[str, Any]) -> Optional[str]:
    # Scopus search usually does not return direct PDFs
    return None


def _normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    doi = entry.get("prism:doi")
    return {
        "id": entry.get("eid") or entry.get("dc:identifier"),
        "title": entry.get("dc:title") or "",
        "authors": _join_authors(entry),
        "journal": entry.get("prism:publicationName") or None,
        "pub_date": entry.get("prism:coverDate") or None,
        "abstract": None,
        "doi": doi,
        "url": entry.get("prism:url") or (f"https://doi.org/{doi}" if doi else None),
        "pdf_url": _pdf_url(entry),
        "provider": "scopus",
    }


def search_scopus(
    q: Optional[str],
    offset: int,
    limit: int,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    open_access_only: bool = False,
) -> Tuple[Optional[List[Dict]], int, Optional[str]]:
    api_key = os.getenv("ELSEVIER_API_KEY")
    if not api_key:
        return None, 0, _missing_key_error()
    try:
        session = _mk_session()
        query_parts: List[str] = []
        if q:
            query_parts.append(q)
        if from_year or to_year:
            lo = from_year or to_year
            hi = to_year or from_year
            if lo and hi and hi < lo:
                lo, hi = hi, lo
            if lo and hi:
                query_parts.append(f"PUBYEAR >={lo} AND PUBYEAR <={hi}")
            elif lo:
                query_parts.append(f"PUBYEAR = {lo}")
        if open_access_only:
            # Best-effort OA filter in Scopus advanced query
            query_parts.append("OPENACCESS(1)")

        params: Dict[str, Any] = {
            "query": " AND ".join(query_parts) if query_parts else "ALL(*)",
            "start": offset,
            "count": limit,
            "view": "STANDARD",
        }
        r = session.get(BASE_URL, headers=_headers(), params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        sr = data.get("search-results") or {}
        total = int((sr.get("opensearch:totalResults") or 0))
        entries = sr.get("entry") or []
        items = [_normalize_entry(e) for e in entries]
        return items, total, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to Scopus API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"Scopus API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to Scopus API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"Scopus API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"Scopus API Request Error: {str(e)}"
        return None, 0, f"Scopus error: {str(e)}"


def get_scopus_by_doi(doi: str) -> Tuple[Optional[Dict], Optional[str]]:
    api_key = os.getenv("ELSEVIER_API_KEY")
    if not api_key:
        return None, _missing_key_error()
    try:
        session = _mk_session()
        params = {
            "query": f"DOI({doi})",
            "start": 0,
            "count": 1,
            "view": "STANDARD",
        }
        r = session.get(BASE_URL, headers=_headers(), params=params, timeout=20)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json() or {}
        sr = data.get("search-results") or {}
        entries = sr.get("entry") or []
        if not entries:
            return None, None
        return _normalize_entry(entries[0]), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to Scopus API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"Scopus API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to Scopus API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"Scopus API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"Scopus API Request Error: {str(e)}"
        return None, f"Scopus error: {str(e)}"
