"""HAL.science Search API adapter (Solr-like).

API docs: https://api.archives-ouvertes.fr/docs/search
Entry point (default): https://api.archives-ouvertes.fr/search/

Supports:
 - JSON search with normalization to GenericPaper-like items
 - Raw passthrough for multiple formats via `wt` (json, xml, xml-tei, csv, bibtex, endnote, atom, rss)
 - By-docid lookup (best-effort)
 - PDF URL extraction from common HAL fields
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


BASE_URL = "https://api.archives-ouvertes.fr/search/"


def _build_url(scope: Optional[str]) -> str:
    if not scope:
        return BASE_URL
    s = str(scope).strip().strip('/')
    if not s:
        return BASE_URL
    return f"{BASE_URL}{s}/"


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


DEFAULT_FL = (
    "docid,label_s,title_s,authFullName_s,doiId_s,abstract_s,"
    "producedDate_tdate,producedDateY_i,uri_s,fileMain_s,files_s,linkExtUrl_s"
)


def _join_authors(doc: Dict[str, Any]) -> Optional[str]:
    try:
        auths = doc.get("authFullName_s")
        if isinstance(auths, list):
            names = [str(a) for a in auths if a]
            return ", ".join(names) if names else None
        if isinstance(auths, str):
            return auths
        return None
    except Exception:
        return None


def _pick_pdf_url(doc: Dict[str, Any]) -> Optional[str]:
    """Heuristically pick a PDF URL from HAL document fields."""
    try:
        # Common fields that may contain URLs
        candidates: List[str] = []
        for key in ("fileMain_s", "linkExtUrl_s", "uri_s"):
            val = doc.get(key)
            if isinstance(val, str):
                candidates.append(val)
        # Multi-valued files
        for key in ("files_s", "enclosures_s"):
            val = doc.get(key)
            if isinstance(val, list):
                for v in val:
                    if isinstance(v, str):
                        candidates.append(v)
        for url in candidates:
            u = url.strip()
            if u.lower().endswith(".pdf"):
                return u
        return None
    except Exception:
        return None


def _normalize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    title = doc.get("title_s") or doc.get("label_s") or ""
    doi = doc.get("doiId_s") or None
    url = doc.get("uri_s") or (f"https://doi.org/{doi}" if doi else None)
    return {
        "id": str(doc.get("docid") or ""),
        "title": title,
        "authors": _join_authors(doc),
        "journal": None,
        "pub_date": doc.get("producedDate_tdate") or None,
        "abstract": doc.get("abstract_s") or None,
        "doi": doi,
        "url": url,
        "pdf_url": _pick_pdf_url(doc),
        "provider": "hal",
    }


def search(
    q: str,
    start: int,
    rows: int,
    fl: Optional[str] = None,
    fq: Optional[List[str]] = None,
    sort: Optional[str] = None,
    scope: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    try:
        s = _mk_session()
        params_list: List[Tuple[str, str]] = [
            ("q", (q or "*:*")),
            ("wt", "json"),
            ("start", str(max(0, start))),
            ("rows", str(max(1, min(rows, 1000)))),
            ("fl", fl or DEFAULT_FL),
        ]
        if sort:
            params_list.append(("sort", sort))
        if fq:
            for f in fq:
                params_list.append(("fq", f))
        url = _build_url(scope)
        r = s.get(url, params=params_list, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        resp = (data.get("response") or {}) if isinstance(data, dict) else {}
        total = int(resp.get("numFound") or 0)
        docs = resp.get("docs") or []
        items = []
        for d in docs:
            if isinstance(d, dict):
                items.append(_normalize_doc(d))
        return items, total, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to HAL API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"HAL API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to HAL API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"HAL API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"HAL API Request Error: {str(e)}"
        return None, 0, f"HAL error: {str(e)}"


def by_docid(docid: str, fl: Optional[str] = None, scope: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        items, _, err = search(q=f"docid:{docid}", start=0, rows=1, fl=fl or DEFAULT_FL, scope=scope)
        if err:
            return None, err
        if items:
            return items[0], None
        return None, None
    except Exception as e:
        return None, f"HAL error: {str(e)}"


def raw(params: Dict[str, Any], scope: Optional[str] = None) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Raw passthrough. Accepts wt in params and returns (content, media_type, error)."""
    try:
        s = _mk_session()
        wt = (params.get("wt") or "json").lower()
        # set Accept to something reasonable; we return upstream content-type anyway
        if wt in ("xml", "xml-tei", "atom", "rss"):
            s.headers.update({"Accept": "application/xml"})
        elif wt in ("csv", "bibtex", "endnote"):
            s.headers.update({"Accept": "text/plain"})
        else:
            s.headers.update({"Accept": "application/json"})

        url = _build_url(scope)
        r = s.get(url, params=params, timeout=25)
        r.raise_for_status()
        ct = r.headers.get("content-type") or "application/octet-stream"
        return r.content, ct.split(";")[0], None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to HAL API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"HAL API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to HAL API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"HAL API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"HAL API Request Error: {str(e)}"
        return None, None, f"HAL error: {str(e)}"


def extract_pdf_from_raw_doc(doc: Dict[str, Any]) -> Optional[str]:
    return _pick_pdf_url(doc)
