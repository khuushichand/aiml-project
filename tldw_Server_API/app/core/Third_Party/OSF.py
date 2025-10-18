"""OSF (Open Science Framework) Preprints API adapter.

Docs: https://developer.osf.io/
Base: https://api.osf.io/v2/preprints/

Supports:
- Search preprints across all providers or a specific provider via filter[provider]
- Lookup by OSF preprint ID or by DOI (best-effort)
- Raw passthrough helpers where needed
- Primary file download URL resolution for ingestion

Notes:
- We avoid per-item subrequests during search for performance; PDF URL is
  resolved on-demand by ingest via primary_file relationship.
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
    osf_id = item.get("id") or ""
    attrs = item.get("attributes") or {}
    links = item.get("links") or {}
    title = attrs.get("title") or ""
    abstract = attrs.get("description") or None
    pub_date = attrs.get("date_published") or attrs.get("date_created")
    doi = (
        attrs.get("doi")
        or attrs.get("preprint_doi")
        or attrs.get("article_doi")
        or None
    )
    url = links.get("html") or (f"https://osf.io/preprints/{osf_id}")
    return {
        "id": osf_id,
        "title": title,
        "authors": None,  # author expansion requires includes; omitted to avoid N+1
        "journal": None,
        "pub_date": pub_date,
        "abstract": abstract,
        "doi": doi,
        "url": url,
        "pdf_url": None,  # resolve via primary file at ingest time
        "provider": "osf",
    }


def search_preprints(
    term: Optional[str],
    page: int,
    results_per_page: int,
    provider: Optional[str] = None,
    from_date: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    """Search OSF preprints, optionally narrowing to a specific provider.

    - `term` maps to OSF's `q` parameter
    - `provider` maps to `filter[provider]`
    - `from_date` maps to `filter[date_created][gte]`
    """
    try:
        session = _mk_session()
        params: Dict[str, Any] = {
            "page[size]": max(1, min(results_per_page, 100)),
            "page[number]": max(1, page),
        }
        if term:
            params["q"] = term
        if provider:
            params["filter[provider]"] = provider
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
        # Total may be present under links.meta.total; otherwise approximate
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
        return None, 0, f"OSF error: {str(e)}"


def get_preprint_by_id(osf_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        session = _mk_session()
        url = f"{BASE_URL}{osf_id}"
        r = session.get(url, timeout=20)
        if r.status_code == 404:
            return None, None
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
        return None, f"OSF error: {str(e)}"


def get_preprint_by_doi(doi: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Lookup preprint by DOI using direct filter and fallback query."""
    try:
        if not doi or not doi.strip():
            return None, "DOI cannot be empty"
        session = _mk_session()
        # Try exact filter on doi and article_doi
        for field in ("doi", "article_doi"):
            params = {"page[size]": 1, f"filter[{field}]": doi}
            r = session.get(BASE_URL, params=params, timeout=20)
            if r.status_code == 200:
                data = r.json() or {}
                items = data.get("data") or []
                if items:
                    return _normalize_item(items[0]), None
        # Fallback free-text search
        r = session.get(BASE_URL, params={"q": doi, "page[size]": 1}, timeout=20)
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
        return None, f"OSF error: {str(e)}"


def get_primary_file_download_url(osf_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Resolve the primary file's direct download URL for a given preprint id.

    Returns (download_url, error).
    """
    try:
        session = _mk_session()
        # 1) Fetch preprint with primary_file relationship link
        r = session.get(f"{BASE_URL}{osf_id}", timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        rel = ((data.get("data") or {}).get("relationships") or {}).get("primary_file") or {}
        rel_links = (rel.get("links") or {}).get("related") or {}
        href = rel_links.get("href")
        if not href:
            # try embeds via include
            r2 = session.get(f"{BASE_URL}{osf_id}?include=primary_file", timeout=20)
            if r2.status_code == 200:
                d2 = r2.json() or {}
                included = d2.get("included") or []
                for inc in included:
                    if inc.get("type") == "files" and inc.get("id"):
                        links = inc.get("links") or {}
                        dl = links.get("download") or links.get("meta", {}).get("download")
                        if dl:
                            return dl, None
            return None, None
        # 2) Follow file endpoint to get download link
        rf = session.get(href, timeout=20)
        rf.raise_for_status()
        fdata = rf.json() or {}
        links = (fdata.get("data") or {}).get("links") or {}
        dl_url = links.get("download") or links.get("meta", {}).get("download")
        return (dl_url or None), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to OSF API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, f"Request to OSF API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"OSF API Request Error: {str(e)}"
        return None, f"OSF error: {str(e)}"


def raw_preprints(params: Dict[str, Any]) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Raw passthrough for OSF preprints list endpoint.

    Accepts a dict of query parameters (e.g., q, filter[provider], page[size], page[number], filter[date_created][gte]).
    Returns (content, media_type, error).
    """
    try:
        s = _mk_session()
        r = s.get(BASE_URL, params=params, timeout=25)
        r.raise_for_status()
        ct = r.headers.get("content-type") or "application/json"
        return r.content, ct.split(";")[0], None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to OSF API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to OSF API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"OSF API Request Error: {str(e)}"
        return None, None, f"OSF error: {str(e)}"


def raw_by_id(osf_id: str) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Raw passthrough for a single OSF preprint by id."""
    try:
        s = _mk_session()
        r = s.get(f"{BASE_URL}{osf_id}", timeout=25)
        if r.status_code == 404:
            return None, "application/json", None
        r.raise_for_status()
        ct = r.headers.get("content-type") or "application/json"
        return r.content, ct.split(";")[0], None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to OSF API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to OSF API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"OSF API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"OSF API Request Error: {str(e)}"
        return None, None, f"OSF error: {str(e)}"
