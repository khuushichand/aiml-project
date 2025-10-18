"""EarthArXiv (EarthRxiv) adapter via OSF Preprints API.

Docs: https://api.osf.io/
Provider key: 'eartharxiv'

We implement simple search and lookup helpers that return a normalized
GenericPaper-like dict. We avoid per-item subrequests; DOI and authors
may be missing in list results. We provide stable html/pdf links that
enable ingest-by-pdf.
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


BASE_URL = "https://api.osf.io/v2/preprints/"
PROVIDER = "eartharxiv"


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
        s.headers.update({"Accept": "application/json"})
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map OSF preprint item to GenericPaper fields.

    We compute EarthArXiv landing and download links from the OSF id.
    """
    osf_id = item.get("id") or ""
    attrs = item.get("attributes") or {}
    title = attrs.get("title") or ""
    abstract = attrs.get("description") or None
    pub_date = attrs.get("date_published") or attrs.get("date_created")
    # DOI can appear in different places depending on OSF; may be missing
    doi = attrs.get("doi") or attrs.get("preprint_doi") or None
    # Build EarthArXiv URLs
    url = f"https://eartharxiv.org/{osf_id}/" if osf_id else None
    pdf_url = f"https://eartharxiv.org/{osf_id}/download" if osf_id else None
    return {
        "id": osf_id,
        "title": title,
        "authors": None,  # Omitted to avoid extra calls; UI still supports ingest
        "journal": None,
        "pub_date": pub_date,
        "abstract": abstract,
        "doi": doi,
        "url": url,
        "pdf_url": pdf_url,
        "provider": "eartharxiv",
    }


def search_items(
    term: Optional[str],
    page: int,
    results_per_page: int,
    from_date: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    try:
        session = _mk_session()
        params: Dict[str, Any] = {
            "filter[provider]": PROVIDER,
            "page[size]": max(1, min(results_per_page, 100)),
            "page[number]": max(1, page),
        }
        if term:
            # OSF supports 'q' across common text fields
            params["q"] = term
        if from_date:
            params["filter[date_created][gte]"] = from_date
        r = session.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        items = [
            _normalize_item(it)
            for it in (data.get("data") or [])
            if isinstance(it, dict)
        ]
        # OSF meta may include total; if missing, approximate
        meta = (data.get("links") or {}).get("meta") or {}
        total = int(meta.get("total") or 0)
        if total == 0:
            total = len(items)
        return items, total, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to OSF API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to OSF API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"OSF API Request Error: {str(e)}"
        return None, 0, f"EarthArXiv error: {str(e)}"


def get_item_by_id(osf_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        session = _mk_session()
        url = f"{BASE_URL}{osf_id}"
        r = session.get(url, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        if isinstance(data.get("data"), dict):
            return _normalize_item(data["data"]), None
        return None, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to OSF API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to OSF API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"OSF API Request Error: {str(e)}"
        return None, f"EarthArXiv error: {str(e)}"


def get_item_by_doi(doi: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        session = _mk_session()
        # Attempt direct DOI filter; fallback to search query
        params: Dict[str, Any] = {
            "filter[provider]": PROVIDER,
            "filter[doi]": doi,
            "page[size]": 1,
        }
        r = session.get(BASE_URL, params=params, timeout=20)
        if r.status_code == 200:
            data = r.json() or {}
            items = data.get("data") or []
            if items:
                return _normalize_item(items[0]), None
        # Fallback: query by DOI string
        r = session.get(BASE_URL, params={"filter[provider]": PROVIDER, "q": doi, "page[size]": 1}, timeout=20)
        r.raise_for_status()
        data2 = r.json() or {}
        items2 = data2.get("data") or []
        if items2:
            return _normalize_item(items2[0]), None
        return None, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to OSF API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to OSF API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"OSF API Request Error: {str(e)}"
        return None, f"EarthArXiv error: {str(e)}"
