"""IEEE Xplore API adapter.

Implements search and lookup with the project’s standard return signatures.
Requires `IEEE_API_KEY` in environment.
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
    return "IEEE API key not configured. Set IEEE_API_KEY to enable this provider."


BASE_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"


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


def _join_authors(authors_block: Any) -> Optional[str]:
    try:
        auths = ((authors_block or {}).get("authors") or [])
        names = []
        for a in auths:
            name = a.get("preferred_name") or a.get("full_name")
            if name:
                names.append(name)
        return ", ".join(names) if names else None
    except Exception:
        return None


def _pdf_url(article: Dict[str, Any]) -> Optional[str]:
    # Prefer pdf_url when present
    if article.get("pdf_url"):
        return article.get("pdf_url")
    # Some responses contain 'html_url' only
    return None


def _normalize_article(article: Dict[str, Any]) -> Dict[str, Any]:
    doi = article.get("doi")
    return {
        "id": str(article.get("article_number") or ""),
        "title": article.get("title") or "",
        "authors": _join_authors(article.get("authors")),
        "journal": article.get("publication_title") or None,
        "pub_date": str(article.get("publication_year") or ""),
        "abstract": article.get("abstract") or None,
        "doi": doi,
        "url": article.get("html_url") or (f"https://doi.org/{doi}" if doi else None),
        "pdf_url": _pdf_url(article),
        "provider": "ieee",
    }


def search_ieee(
    q: Optional[str],
    offset: int,
    limit: int,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    publication_title: Optional[str] = None,
    authors: Optional[str] = None,
) -> Tuple[Optional[List[Dict]], int, Optional[str]]:
    api_key = os.getenv("IEEE_API_KEY")
    if not api_key:
        return None, 0, _missing_key_error()
    try:
        session = _mk_session()
        # IEEE uses 1-based start_record; limit via max_records
        start_record = max(1, offset + 1)
        params: Dict[str, Any] = {
            "apikey": api_key,
            "format": "json",
            "start_record": start_record,
            "max_records": limit,
        }
        # Build querytext combining free text and author/publication if provided
        q_parts: List[str] = []
        if q:
            q_parts.append(q)
        if authors:
            q_parts.append(f"authors:{authors}")
        if publication_title:
            q_parts.append(f"publication_title:{publication_title}")
        if q_parts:
            params["querytext"] = " AND ".join(q_parts)
        # Year range
        if from_year or to_year:
            lo = from_year or to_year
            hi = to_year or from_year
            if lo and hi and hi < lo:
                lo, hi = hi, lo
            if lo and hi:
                params["publication_year"] = f"{lo}_{hi}"
            elif lo:
                params["publication_year"] = f"{lo}_{lo}"

        r = session.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        total = int(data.get("total_records") or 0)
        articles = data.get("articles") or []
        items = [_normalize_article(it) for it in articles]
        return items, total, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to IEEE Xplore API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"IEEE Xplore API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to IEEE Xplore API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"IEEE Xplore API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"IEEE Xplore API Request Error: {str(e)}"
        return None, 0, f"IEEE Xplore error: {str(e)}"


def get_ieee_by_doi(doi: str) -> Tuple[Optional[Dict], Optional[str]]:
    api_key = os.getenv("IEEE_API_KEY")
    if not api_key:
        return None, _missing_key_error()
    try:
        session = _mk_session()
        params = {
            "apikey": api_key,
            "format": "json",
            "max_records": 1,
            # Use querytext targeting DOI; IEEE search supports doi in querytext
            "querytext": f"doi:{doi}",
        }
        r = session.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        articles = data.get("articles") or []
        if not articles:
            return None, None
        return _normalize_article(articles[0]), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to IEEE Xplore API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"IEEE Xplore API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to IEEE Xplore API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"IEEE Xplore API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"IEEE Xplore API Request Error: {str(e)}"
        return None, f"IEEE Xplore error: {str(e)}"


def get_ieee_by_id(article_number: str) -> Tuple[Optional[Dict], Optional[str]]:
    api_key = os.getenv("IEEE_API_KEY")
    if not api_key:
        return None, _missing_key_error()
    try:
        session = _mk_session()
        params = {
            "apikey": api_key,
            "format": "json",
            "max_records": 1,
            # arnumber is the field commonly used for IEEE article number
            "querytext": f"arnumber:{article_number}",
        }
        r = session.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        articles = data.get("articles") or []
        if not articles:
            return None, None
        return _normalize_article(articles[0]), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to IEEE Xplore API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"IEEE Xplore API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to IEEE Xplore API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"IEEE Xplore API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"IEEE Xplore API Request Error: {str(e)}"
        return None, f"IEEE Xplore error: {str(e)}"
