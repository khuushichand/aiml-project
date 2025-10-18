"""Zenodo API adapter (Records + OAI-PMH passthrough).

Search published records via https://zenodo.org/api/records and normalize to
GenericPaper-like objects. Also provides by-id and by-doi helpers and an
OAI-PMH raw passthrough for XML.
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


RECORDS_URL = "https://zenodo.org/api/records"
OAI_BASE = "https://zenodo.org/oai2d"


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


def _join_authors(meta: Dict[str, Any]) -> Optional[str]:
    try:
        creators = meta.get("creators") or []
        names = []
        for c in creators:
            nm = (c or {}).get("name") or ""
            if nm:
                names.append(nm)
        return ", ".join(names) if names else None
    except Exception:
        return None


def _pick_pdf_url(rec: Dict[str, Any]) -> Optional[str]:
    try:
        files = rec.get("files") or []
        # New API variants may nest under rec["files"][i]["links"]["self"]
        for f in files:
            key = (f or {}).get("key") or (f or {}).get("filename") or ""
            mimetype = (f or {}).get("mimetype") or (f or {}).get("type") or ""
            links = (f or {}).get("links") or {}
            href = links.get("self") or links.get("download")
            if (key and key.lower().endswith(".pdf")) or (mimetype and "pdf" in mimetype.lower()):
                return href or None
        return None
    except Exception:
        return None


def _normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    meta = rec.get("metadata") or {}
    doi = meta.get("doi") or None
    title = meta.get("title") or rec.get("title") or ""
    url = (rec.get("links") or {}).get("html") or (f"https://doi.org/{doi}" if doi else None)
    pdf_url = _pick_pdf_url(rec)
    return {
        "id": str(rec.get("id") or rec.get("record_id") or ""),
        "title": title,
        "authors": _join_authors(meta),
        "journal": meta.get("journal_title") or None,
        "pub_date": meta.get("publication_date") or None,
        "abstract": meta.get("description") or None,
        "doi": doi,
        "url": url,
        "pdf_url": pdf_url,
        "provider": "zenodo",
    }


def search_records(
    q: Optional[str],
    page: int,
    size: int,
    type_: Optional[str] = None,
    subtype: Optional[str] = None,
    communities: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    try:
        session = _mk_session()
        params: Dict[str, Any] = {
            "page": max(1, page),
            "size": max(1, min(size, 100)),
        }
        if q:
            params["q"] = q
        if type_:
            params["type"] = type_
        if subtype:
            params["subtype"] = subtype
        if communities:
            params["communities"] = communities
        r = session.get(RECORDS_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        # Zenodo may return plain list or hits dict depending on version
        hits_block = data.get("hits") if isinstance(data, dict) else None
        if hits_block and isinstance(hits_block, dict):
            hits = hits_block.get("hits") or []
            total = int((hits_block.get("total") or {}).get("value") or hits_block.get("total") or len(hits))
        elif isinstance(data, list):
            hits = data
            total = len(hits)
        else:
            # Fallback: assume top-level has 'hits'
            hits = data.get("hits", []) if isinstance(data, dict) else []
            total = len(hits)
        items = [_normalize_record(h) for h in hits if isinstance(h, dict)]
        return items, total, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to Zenodo API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"Zenodo API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to Zenodo API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"Zenodo API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"Zenodo API Request Error: {str(e)}"
        return None, 0, f"Zenodo error: {str(e)}"


def get_record_by_id(record_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        session = _mk_session()
        r = session.get(f"{RECORDS_URL}/{record_id}", timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        return _normalize_record(data), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to Zenodo API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"Zenodo API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to Zenodo API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"Zenodo API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"Zenodo API Request Error: {str(e)}"
        return None, f"Zenodo error: {str(e)}"


def get_record_by_doi(doi: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        session = _mk_session()
        # Search by DOI string
        params = {"q": doi, "size": 1}
        r = session.get(RECORDS_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        hits_block = data.get("hits") if isinstance(data, dict) else None
        items = []
        if hits_block and isinstance(hits_block, dict):
            items = hits_block.get("hits") or []
        elif isinstance(data, list):
            items = data
        if items:
            return _normalize_record(items[0]), None
        return None, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to Zenodo API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"Zenodo API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to Zenodo API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"Zenodo API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"Zenodo API Request Error: {str(e)}"
        return None, f"Zenodo error: {str(e)}"


def oai_raw(params: Dict[str, Any]) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    try:
        s = _mk_session()
        # For OAI, accept XML
        s.headers.update({"Accept": "application/xml"})
        r = s.get(OAI_BASE, params=params, timeout=20)
        r.raise_for_status()
        ct = r.headers.get("content-type") or "application/xml"
        return r.content, ct.split(";")[0], None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to Zenodo OAI-PMH timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"Zenodo OAI-PMH HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to Zenodo OAI-PMH timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"Zenodo OAI-PMH HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"Zenodo OAI-PMH Request Error: {str(e)}"
        return None, None, f"Zenodo OAI-PMH error: {str(e)}"


def get_record_raw(record_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return the raw Zenodo record JSON for advanced inspection (e.g., files)."""
    try:
        session = _mk_session()
        r = session.get(f"{RECORDS_URL}/{record_id}", timeout=20)
        r.raise_for_status()
        return r.json() or {}, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to Zenodo API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"Zenodo API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, f"Request to Zenodo API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"Zenodo API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"Zenodo API Request Error: {str(e)}"
        return None, f"Zenodo error: {str(e)}"


def extract_pdf_from_raw(rec: Dict[str, Any]) -> Optional[str]:
    """Find a PDF download link from raw record JSON if present."""
    try:
        files = rec.get("files") or []
        for f in files:
            links = (f or {}).get("links") or {}
            href = links.get("self") or links.get("download")
            mimetype = (f or {}).get("mimetype") or (f or {}).get("type") or ""
            key = (f or {}).get("key") or (f or {}).get("filename") or ""
            if ((key and key.lower().endswith('.pdf')) or (mimetype and 'pdf' in mimetype.lower())) and href:
                return href
        return None
    except Exception:
        return None
