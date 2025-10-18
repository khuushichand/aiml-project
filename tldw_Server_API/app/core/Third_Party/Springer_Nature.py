"""Springer Nature Metadata API adapter.

Return signature follows project convention. Requires `SPRINGER_NATURE_API_KEY`.
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
    return "Springer Nature API key not configured. Set SPRINGER_NATURE_API_KEY."


BASE_URL = "https://api.springernature.com/metadata/json"


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


def _join_authors(creators: Any) -> Optional[str]:
    try:
        names = []
        for c in creators or []:
            name = c.get("creator")
            if name:
                names.append(name)
        return ", ".join(names) if names else None
    except Exception:
        return None


def _pdf_url(urls: Any) -> Optional[str]:
    for u in urls or []:
        if (u.get("format") or "").lower() == "pdf":
            if u.get("value"):
                return u.get("value")
    return None


def _normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    doi = rec.get("doi")
    return {
        "id": doi or rec.get("identifier"),
        "title": rec.get("title") or "",
        "authors": _join_authors(rec.get("creators")),
        "journal": rec.get("publicationName") or None,
        "pub_date": rec.get("publicationDate") or None,
        "abstract": rec.get("abstract") or None,
        "doi": doi,
        "url": (rec.get("url") or [{}])[0].get("value") if isinstance(rec.get("url"), list) else None,
        "pdf_url": _pdf_url(rec.get("url")),
        "provider": "springer",
    }


def search_springer(
    q: Optional[str],
    offset: int,
    limit: int,
    journal: Optional[str] = None,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
) -> Tuple[Optional[List[Dict]], int, Optional[str]]:
    api_key = os.getenv("SPRINGER_NATURE_API_KEY")
    if not api_key:
        return None, 0, _missing_key_error()
    try:
        session = _mk_session()
        # Springer uses 'q' with fielded query; 'p' page size, 's' start index
        q_parts: List[str] = []
        if q:
            q_parts.append(q)
        if journal:
            # Field often called 'journal' in examples; alternatively 'publicationName'
            q_parts.append(f"journal:\"{journal}\"")
        if from_year or to_year:
            lo = from_year or to_year
            hi = to_year or from_year
            if lo and hi and hi < lo:
                lo, hi = hi, lo
            if lo and hi:
                q_parts.append(f"year:{lo}-{hi}")
            elif lo:
                q_parts.append(f"year:{lo}")

        params: Dict[str, Any] = {
            "api_key": api_key,
            "p": limit,
            "s": offset,
            "q": " AND ".join(q_parts) if q_parts else "*",
        }
        r = session.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        message = data.get("result") or []
        # total items can be found in the first element's 'total' typically
        total = 0
        if message and isinstance(message, list):
            try:
                total = int((message[0] or {}).get("total") or 0)
            except Exception:
                total = 0
        records = data.get("records") or []
        items = [_normalize_record(rec) for rec in records]
        return items, total, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to Springer API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"Springer API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to Springer API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"Springer API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"Springer API Request Error: {str(e)}"
        return None, 0, f"Springer error: {str(e)}"


def get_springer_by_doi(doi: str) -> Tuple[Optional[Dict], Optional[str]]:
    api_key = os.getenv("SPRINGER_NATURE_API_KEY")
    if not api_key:
        return None, _missing_key_error()
    try:
        session = _mk_session()
        params = {
            "api_key": api_key,
            "p": 1,
            "s": 0,
            "q": f"doi:{doi}",
        }
        r = session.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        records = data.get("records") or []
        if not records:
            return None, None
        return _normalize_record(records[0]), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to Springer API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"Springer API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to Springer API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"Springer API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"Springer API Request Error: {str(e)}"
        return None, f"Springer error: {str(e)}"
