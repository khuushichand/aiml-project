"""ChemRxiv Public API adapter.

Docs (Swagger 2): host chemrxiv.org, basePath /engage/chemrxiv/public-api/v1
Endpoints used:
 - GET /items (search)
 - GET /items/{itemId}
 - GET /items/doi/{doi}
 - GET /categories
 - GET /licenses
 - GET /version
 - GET /oai (raw, OAI-PMH XML)
"""
from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import quote as urlquote
from tldw_Server_API.app.core.http_client import fetch, fetch_json


BASE_URL = "https://chemrxiv.org/engage/chemrxiv/public-api/v1"


def _join_authors(authors: Any) -> Optional[str]:
    try:
        names = []
        for a in authors or []:
            first = (a or {}).get("firstName") or ""
            last = (a or {}).get("lastName") or ""
            nm = (first + " " + last).strip()
            if nm:
                names.append(nm)
        return ", ".join(names) if names else None
    except Exception:
        return None


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    doi = item.get("doi")
    title = item.get("title") or ""
    url = None
    # Prefer webLinks.url if present
    links = item.get("webLinks") or []
    if links and isinstance(links, list):
        url = (links[0] or {}).get("url")
    if not url and doi:
        url = f"https://doi.org/{doi}"
    return {
        "id": item.get("id") or item.get("legacyId"),
        "title": title,
        "authors": _join_authors(item.get("authors")),
        "journal": None,
        "pub_date": item.get("publishedDate") or item.get("submittedDate"),
        "abstract": item.get("abstract"),
        "doi": doi,
        "url": url,
        "pdf_url": None,
        "provider": "chemrxiv",
    }


def search_items(
    term: Optional[str],
    skip: int,
    limit: int,
    sort: Optional[str] = None,
    author: Optional[str] = None,
    searchDateFrom: Optional[str] = None,
    searchDateTo: Optional[str] = None,
    searchLicense: Optional[str] = None,
    categoryIds: Optional[List[str]] = None,
    subjectIds: Optional[List[str]] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    try:
        url = f"{BASE_URL}/items"
        params: Dict[str, Any] = {
            "skip": max(0, skip),
            "limit": min(max(1, limit), 50),
        }
        if term:
            params["term"] = term
        if sort:
            params["sort"] = sort
        if author:
            params["author"] = author
        if searchDateFrom:
            params["searchDateFrom"] = searchDateFrom
        if searchDateTo:
            params["searchDateTo"] = searchDateTo
        if searchLicense:
            params["searchLicense"] = searchLicense
        if categoryIds:
            for cid in categoryIds:
                params.setdefault("categoryIds", []).append(cid)
        if subjectIds:
            for sid in subjectIds:
                params.setdefault("subjectIds", []).append(sid)

        data = fetch_json(method="GET", url=url, params=params, timeout=20)
        total = int(data.get("totalCount") or 0)
        hits = data.get("itemHits") or []
        # Each hit may wrap details or already be the item; best-effort unwrap
        items = []
        for h in hits:
            if isinstance(h, dict) and "title" in h:
                items.append(_normalize_item(h))
            elif isinstance(h, dict):
                # Fallback if nested under a key
                for v in h.values():
                    if isinstance(v, dict) and "title" in v:
                        items.append(_normalize_item(v))
                        break
        return items, total, None
    except Exception as e:
        return None, 0, f"ChemRxiv error: {str(e)}"


def get_item_by_id(item_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        url = f"{BASE_URL}/items/{item_id}"
        r = fetch(method="GET", url=url, timeout=20)
        if r.status_code == 410:
            return None, None
        if r.status_code >= 400:
            return None, f"ChemRxiv HTTP error: {r.status_code}"
        data = r.json() or {}
        return _normalize_item(data), None
    except Exception as e:
        return None, f"ChemRxiv error: {str(e)}"


def get_item_by_doi(doi: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        doi_enc = urlquote(doi.strip(), safe="/")
        url = f"{BASE_URL}/items/doi/{doi_enc}"
        r = fetch(method="GET", url=url, timeout=20)
        if r.status_code == 410:
            return None, None
        if r.status_code >= 400:
            return None, f"ChemRxiv HTTP error: {r.status_code}"
        data = r.json() or {}
        return _normalize_item(data), None
    except Exception as e:
        return None, f"ChemRxiv error: {str(e)}"


def get_categories() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        data = fetch_json(method="GET", url=f"{BASE_URL}/categories", timeout=20)
        return data, None
    except Exception as e:
        return None, f"ChemRxiv error: {str(e)}"


def get_licenses() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        session = _mk_session()
        r = session.get(f"{BASE_URL}/licenses", timeout=20)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, f"Request to ChemRxiv API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"ChemRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, f"Request to ChemRxiv API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"ChemRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"ChemRxiv API Request Error: {str(e)}"
        return None, f"ChemRxiv error: {str(e)}"


def get_version() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        session = _mk_session()
        r = session.get(f"{BASE_URL}/version", timeout=20)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.Timeout:
        return None, "Request to ChemRxiv API timed out."
    except requests.exceptions.HTTPError as e:
        return None, f"ChemRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
    except requests.exceptions.RequestException as e:
        return None, f"ChemRxiv API Request Error: {str(e)}"
    except Exception as e:
        return None, f"ChemRxiv error: {str(e)}"


def oai_raw(params: Dict[str, Any]) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Raw OAI-PMH passthrough. Returns (content, media_type, error)."""
    try:
        session = _mk_session()
        url = f"{BASE_URL}/oai"
        r = session.get(url, params=params, timeout=20)
        r.raise_for_status()
        ct = r.headers.get("content-type") or "application/xml"
        return r.content, ct.split(";")[0], None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to ChemRxiv API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"ChemRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to ChemRxiv API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"ChemRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"ChemRxiv API Request Error: {str(e)}"
        return None, None, f"ChemRxiv error: {str(e)}"
