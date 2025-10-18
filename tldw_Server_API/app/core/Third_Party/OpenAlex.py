"""OpenAlex client for venue-constrained searches (ACM/Wiley/etc.).

No API key required. Implements basic search and DOI lookup with retries and
standardized return signatures expected by the API layer.
"""
from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any
import os
import math
import requests
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tldw_Server_API.app.core.http_client import create_client


BASE_URL = "https://api.openalex.org"


def _mk_session():
    try:
        c = create_client(timeout=20)
        mailto = os.getenv("OPENALEX_MAILTO")
        ua = "tldw_server/0.1 (+https://github.com/openai/tldw_server)"
        headers = {"Accept": "application/json", "User-Agent": ua}
        c.headers.update(headers)
        return c
    except Exception:
        retry_strategy = Retry(
            total=5,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        s = requests.Session()
        mailto = os.getenv("OPENALEX_MAILTO")
        ua = "tldw_server/0.1 (+https://github.com/openai/tldw_server)"
        headers = {"Accept": "application/json", "User-Agent": ua}
        s.headers.update(headers)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s


def _norm_authors(authorships: Any) -> Optional[str]:
    try:
        names = []
        for a in authorships or []:
            author = (a or {}).get("author") or {}
            name = author.get("display_name")
            if name:
                names.append(name)
        return ", ".join(names) if names else None
    except Exception:
        return None


def _norm_venue(result: Dict[str, Any]) -> Optional[str]:
    hv = result.get("host_venue") or {}
    name = hv.get("display_name")
    if name:
        return name
    pl = result.get("primary_location") or {}
    src = pl.get("source") or {}
    name = src.get("display_name")
    return name or None


def _norm_pdf_url(result: Dict[str, Any]) -> Optional[str]:
    # OpenAlex has open_access.oa_url or best_oa_location.url
    oa = result.get("open_access") or {}
    if oa.get("oa_url"):
        return oa.get("oa_url")
    bol = result.get("best_oa_location") or {}
    url = bol.get("url_for_pdf") or bol.get("url")
    return url or None


def _norm_url(result: Dict[str, Any]) -> Optional[str]:
    # Prefer DOI link; fallback landing page
    doi = result.get("doi")
    if isinstance(doi, str) and doi:
        return f"https://doi.org/{doi.split('doi.org/')[-1] if 'doi.org' in doi else doi}"
    pl = result.get("primary_location") or {}
    return pl.get("landing_page_url") or None


def _normalize_openalex_work(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": result.get("id"),
        "title": result.get("title") or "",
        "authors": _norm_authors(result.get("authorships")),
        "journal": _norm_venue(result),
        "pub_date": result.get("publication_date") or str(result.get("publication_year") or ""),
        "abstract": None,  # abstract_inverted_index is non-trivial to reconstruct
        "doi": (result.get("doi") or "").replace("https://doi.org/", ""),
        "url": _norm_url(result),
        "pdf_url": _norm_pdf_url(result),
        "provider": "openalex",
    }


def search_openalex(
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
        page = math.floor(offset / max(1, limit)) + 1
        filters = []
        if from_year:
            filters.append(f"from_publication_date:{from_year}-01-01")
        if to_year:
            filters.append(f"to_publication_date:{to_year}-12-31")
        if filter_venue:
            filters.append(f"host_venue.display_name.search:{filter_venue}")

        params: Dict[str, Any] = {"per-page": limit, "page": page}
        if q:
            params["search"] = q
        if filters:
            params["filter"] = ",".join(filters)
        # Add mailto param if provided via env (improves reliability and rate limits)
        mailto = os.getenv("OPENALEX_MAILTO")
        if mailto:
            params["mailto"] = mailto

        r = session.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        total = (data.get("meta") or {}).get("count") or 0
        items = [_normalize_openalex_work(it) for it in results]
        return items, int(total), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to OpenAlex API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"OpenAlex API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to OpenAlex API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"OpenAlex API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"OpenAlex API Request Error: {str(e)}"
        return None, 0, f"OpenAlex error: {str(e)}"


def get_openalex_by_doi(doi: str) -> Tuple[Optional[Dict], Optional[str]]:
    try:
        session = _mk_session()
        doi_clean = doi.strip()
        url = f"{BASE_URL}/works/doi:{doi_clean}"
        r = session.get(url, timeout=20)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json()
        return _normalize_openalex_work(data), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to OpenAlex API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"OpenAlex API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to OpenAlex API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"OpenAlex API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"OpenAlex API Request Error: {str(e)}"
        return None, f"OpenAlex error: {str(e)}"


# Remove duplicate stubs (implementation above)
