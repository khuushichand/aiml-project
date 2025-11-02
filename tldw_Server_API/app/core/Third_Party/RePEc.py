"""RePEc (IDEAS) + CitEc adapter.

This module provides thin wrappers to:
  - IDEAS RePEc API (requires an access code): metadata lookup by handle.
  - CitEc open API: citation counts and AMF by RePEc handle.

Return signatures follow the project convention:
  - Search-like/list calls: (items: List[Dict] | None, total: int, error: str | None)
  - Lookup calls: (item: Dict | None, error: str | None)

Notes
-----
- The IDEAS API is not open; you must set `REPEC_API_CODE` to enable.
- There is no official search endpoint in the IDEAS API; only lookups/functions
  unlocked per account (e.g., getref, getrecentpapers, etc.). We implement
  getref-by-handle support. Other functions can be added later if needed.
- The CitEc API is open and returns XML. We support the `plain` summary and
  passthrough of `amf` payload.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
import requests
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tldw_Server_API.app.core.http_client import create_client
import xml.etree.ElementTree as ET


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
        s.headers.update({"Accept-Encoding": "gzip, deflate"})
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s


# ---------------- IDEAS (RePEc) API: handle -> reference metadata ----------------

def _repec_not_configured() -> str:
    return (
        "RePEc/IDEAS API not configured. Set REPEC_API_CODE to enable this provider."
    )


def _normalize_getref_payload(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single getref JSON object to GenericPaper shape.

    Based on API examples documented on IDEAS (title, author string, abstract,
    handle, link list with Full text/pdf, creationdate, etc.).
    """
    title = obj.get("title") or ""
    authors_raw = obj.get("author")  # often "Last, First & Last2, First2"
    authors = None
    if isinstance(authors_raw, str) and authors_raw.strip():
        # Convert 'A & B & C' -> 'A, B, C'
        authors = ", ".join([p.strip() for p in authors_raw.split("&")])
    abstract = obj.get("abstract") or None
    handle = obj.get("handle") or None
    creationdate = obj.get("creationdate") or None
    revisiondate = obj.get("revisiondate") or None
    pub_date = creationdate or revisiondate

    # Attempt to find a PDF link from link array
    pdf_url: Optional[str] = None
    for lk in (obj.get("link") or []):
        try:
            if (lk.get("function") or "").lower() == "full text":
                if (lk.get("format") or "").lower() in ("application/pdf", "pdf"):
                    if lk.get("url"):
                        pdf_url = lk.get("url")
                        break
        except Exception:
            continue

    return {
        "id": handle or title,
        "title": title,
        "authors": authors,
        "journal": None,  # Not typically present in getref for WPs
        "pub_date": pub_date,
        "abstract": abstract,
        "doi": None,  # Not exposed in sample getref payloads
        "url": None,  # IDEAS page URL mapping from handle is non-trivial; omit
        "pdf_url": pdf_url,
        "provider": "repec",
    }


def get_ref_by_handle(handle: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Lookup a single RePEc item by handle using IDEAS API (`getref`).

    Requires env var `REPEC_API_CODE`.
    Returns (item_dict, error_message) where item_dict matches GenericPaper shape.
    """
    code = os.getenv("REPEC_API_CODE")
    if not code:
        return None, _repec_not_configured()
    try:
        # The exact CGI endpoint for function calls is only documented post-approval.
        # We conservatively route via a generic dispatcher endpoint name likely to be
        # stable; adjust if needed once access is provisioned.
        # Example function: getref; parameters: code, handle
        # If this endpoint shape changes, adapt the URL/params accordingly.
        session = _mk_session()
        url = "https://ideas.repec.org/cgi-bin/getref.cgi"
        params: Dict[str, Any] = {"code": code, "handle": handle}
        r = session.get(url, params=params, timeout=20)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
        if not data or not isinstance(data, list) or not data:
            # Some implementations may return a single object; support both
            if isinstance(data, dict):
                return _normalize_getref_payload(data), None
            return None, "RePEc getref returned no data or unsupported format."
        obj = data[0]
        if isinstance(obj, dict) and obj.get("errornumber"):
            return None, f"RePEc API error: {obj.get('errornumber')}"
        return _normalize_getref_payload(obj), None
    except ValueError:
        return None, "RePEc getref response was not valid JSON."
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "RePEc getref request timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"RePEc getref HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "RePEc getref request timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"RePEc getref HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"RePEc getref Request Error: {str(e)}"
        return None, f"RePEc getref error: {str(e)}"


# ---------------- CitEc API: citations for a RePEc handle ----------------

_CITEC_BASE = "http://citec.repec.org/api"


def get_citations_plain(handle: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Fetch citation summary for a RePEc handle using CitEc `plain` endpoint.

    Returns a dict like: {"handle", "cited_by", "cites", "uri", "date"}
    or (None, error_message) on failures.
    """
    try:
        session = _mk_session()
        url = f"{_CITEC_BASE}/plain/{handle}"
        r = session.get(url, timeout=20)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        text = r.text or ""
        if not text.strip():
            return None, "CitEc returned empty response."
        # Parse XML
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            # Some responses may be HTML-wrapped or XSL transformed; treat as error
            return None, "CitEc response not XML in 'plain' mode."
        # Expected structure: <citationData id="..."><date>...</date><uri>...</uri><citedBy>n</citedBy><cites>m</cites></citationData>
        out: Dict[str, Any] = {"handle": None, "cited_by": 0, "cites": 0, "uri": None, "date": None}
        if root.tag == "errorString":
            return None, root.text or "CitEc error"
        if root.tag != "citationData":
            # In case wrapped, try to find
            cd = root.find("citationData")
            if cd is None:
                return None, "CitEc 'plain' response missing citationData element."
            root = cd
        out["handle"] = root.attrib.get("id")
        for child in root:
            tag = (child.tag or "").lower()
            if tag == "date":
                out["date"] = (child.text or "").strip() or None
            elif tag == "uri":
                out["uri"] = (child.text or "").strip() or None
            elif tag == "citedby":
                try:
                    out["cited_by"] = int((child.text or "0").strip() or 0)
                except Exception:
                    out["cited_by"] = 0
            elif tag == "cites":
                try:
                    out["cites"] = int((child.text or "0").strip() or 0)
                except Exception:
                    out["cites"] = 0
        return out, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "CitEc request timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"CitEc HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "CitEc request timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"CitEc HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"CitEc Request Error: {str(e)}"
        return None, f"CitEc error: {str(e)}"


def get_citations_amf_raw(handle: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch the AMF record for citations/references for a handle.

    Returns (xml_text, error_message). On success, xml_text is a string.
    """
    try:
        session = _mk_session()
        url = f"{_CITEC_BASE}/amf/{handle}"
        r = session.get(url, timeout=20)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        return r.text, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "CitEc request timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"CitEc HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "CitEc request timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"CitEc HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"CitEc Request Error: {str(e)}"
        return None, f"CitEc error: {str(e)}"
