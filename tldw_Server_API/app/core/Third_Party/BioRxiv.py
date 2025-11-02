# BioRxiv.py
# Description: Functions to search BioRxiv/MedRxiv APIs with retries, timeouts, and
#              a normalized response shape used by paper-search endpoints.

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover - optional
    httpx = None  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from tldw_Server_API.app.core.http_client import create_client


BIO_RXIV_API_BASE = "https://api.biorxiv.org"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(d: Optional[str]) -> Optional[str]:
    if d and _DATE_RE.match(d):
        return d
    return None


def _default_date_range() -> Tuple[str, str]:
    # Default to last 30 days if user did not specify
    end = datetime.utcnow().date()
    start = end - timedelta(days=30)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _mk_session():
    try:
        return create_client(timeout=15)
    except Exception:
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        s = requests.Session()
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s


def _media_type_for_format(fmt: str) -> str:
    f = (fmt or "json").lower()
    if f == "json":
        return "application/json"
    if f in ("xml", "oai"):
        return "application/xml"
    if f == "html":
        return "text/html"
    if f == "csv":
        return "text/csv"
    return "application/octet-stream"


def _raw_get(path: str, fmt: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Low-level fetch for passthrough endpoints. Returns (content, media_type, error)."""
    try:
        session = _mk_session()
        url = f"{BIO_RXIV_API_BASE}{path}{('/' + fmt) if fmt else ''}"
        resp = session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        # Prefer declared format for media type to satisfy caller expectations (CSV/XML/HTML)
        media_type = _media_type_for_format(fmt or "json")
        return resp.content, media_type, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to BioRxiv API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to BioRxiv API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"BioRxiv API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"BioRxiv API Request Error: {str(e)}"
        return None, None, f"Unexpected error during BioRxiv raw fetch: {str(e)}"


def _normalize_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Expected fields from BioRxiv API (best-effort):
    # doi, title, authors, category, date, abstract, server, version
    doi = raw.get("doi") or ""
    server = (raw.get("server") or "biorxiv").lower()
    version = raw.get("version")
    # Build canonical content and PDF URLs when possible
    base_host = "biorxiv.org" if server == "biorxiv" else "medrxiv.org"
    content_url = None
    pdf_url = None
    if doi:
        # BioRxiv uses content/{doi}v{version}
        try:
            v_suffix = f"v{int(version)}" if str(version).isdigit() else ""
        except Exception:
            v_suffix = ""
        content_url = f"https://www.{base_host}/content/{doi}{v_suffix}" if v_suffix else f"https://www.{base_host}/content/{doi}"
        pdf_url = f"{content_url}.full.pdf" if content_url else None

    return {
        "doi": doi,
        "title": raw.get("title") or "N/A",
        "authors": raw.get("authors") or "",
        "category": raw.get("category"),
        "date": raw.get("date"),
        "abstract": raw.get("abstract"),
        "server": server,
        "version": version if isinstance(version, int) or (isinstance(version, str) and version.isdigit()) else None,
        "url": content_url,
        "pdf_url": pdf_url,
    }


def _normalize_published_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize /pubs record to a consistent shape for the API layer."""
    return {
        "biorxiv_doi": raw.get("biorxiv_doi") or raw.get("preprint_doi") or "",
        "published_doi": raw.get("published_doi"),
        "published_journal": raw.get("published_journal"),
        "preprint_platform": raw.get("preprint_platform"),
        "preprint_title": raw.get("preprint_title"),
        "preprint_authors": raw.get("preprint_authors"),
        "preprint_category": raw.get("preprint_category"),
        "preprint_date": raw.get("preprint_date"),
        "published_date": raw.get("published_date"),
        "preprint_abstract": raw.get("preprint_abstract"),
        "preprint_author_corresponding": raw.get("preprint_author_corresponding"),
        "preprint_author_corresponding_institution": raw.get("preprint_author_corresponding_institution"),
    }


def search_biorxiv(
    query: Optional[str],
    server: str = "biorxiv",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    category: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
    recent_days: Optional[int] = None,
    recent_count: Optional[int] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    """
    Search BioRxiv/MedRxiv API and return (items, total_results, error_message).

    - When query is provided, use the search endpoint.
    - Otherwise, list details for the date range.

    This function attempts to be robust but is implemented conservatively; callers
    should treat network errors and timeouts as transient and show friendly errors.
    """
    try:
        server_norm = server.lower().strip() if server else "biorxiv"
        if server_norm not in {"biorxiv", "medrxiv"}:
            server_norm = "biorxiv"

        f = _validate_date(from_date)
        t = _validate_date(to_date)
        if not (f and t):
            f, t = _default_date_range()

        # BioRxiv API paginates in steps of 100 (cursor style). We align to that, then slice.
        BATCH = 100
        first_cursor = (offset // BATCH) * BATCH
        within_batch_offset = offset - first_cursor

        session = _mk_session()

        def _details_path(cursor: int) -> str:
            # Support date range or numeric intervals (N or Nd)
            if recent_days and recent_days > 0:
                interval = f"{recent_days}d"
                return f"/details/{server_norm}/{interval}/{cursor}"
            if recent_count and recent_count > 0:
                interval = str(recent_count)
                return f"/details/{server_norm}/{interval}/{cursor}"
            return f"/details/{server_norm}/{f}/{t}/{cursor}"

        def _fetch(cursor: int) -> Tuple[List[Dict[str, Any]], int]:
            # Rely on /details; apply keyword/category filters client-side; pass category as query param too when possible
            path = _details_path(cursor)
            url = f"{BIO_RXIV_API_BASE}{path}"
            params = None
            # Docs indicate the date-range details endpoint accepts category as querystring
            if category and category.strip():
                # BioRxiv accepts underscore instead of spaces
                cat_value = category.strip().replace(" ", "_")
                params = {"category": cat_value}
            resp = session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json() if resp.headers.get("content-type", "").lower().startswith("application/json") else resp.json()

            # API returns messages list with a dict containing count
            total = 0
            msgs = data.get("messages") or []
            if isinstance(msgs, list) and msgs:
                msg0 = msgs[0]
                if isinstance(msg0, dict) and "count" in msg0:
                    try:
                        total = int(msg0["count"])  # may be string
                    except Exception:
                        total = 0
                # Prefer overall total if available
                if isinstance(msg0, dict) and "total" in msg0:
                    try:
                        total = int(msg0["total"])  # total across date range
                    except Exception:
                        pass

            collection = data.get("collection") or []
            normed = [_normalize_item(item) for item in collection]
            # Be a good citizen: tiny delay to avoid hammering
            time.sleep(0.2)
            return normed, total

        # Gather enough batches to satisfy post-filter slicing
        collected: List[Dict[str, Any]] = []
        cursor = first_cursor
        max_batches = 5  # safety cap
        batches = 0
        total = 0
        while batches < max_batches and len(collected) < (within_batch_offset + limit):
            batch_items, total_val = _fetch(cursor)
            if total == 0:
                total = total_val
            # Apply client-side filters (ensure results reflect requested filters even if server ignores params)
            if query and query.strip():
                ql = query.strip().lower()
                def _match(item: Dict[str, Any]) -> bool:
                    return (
                        (item.get("title") or "").lower().find(ql) >= 0
                        or (item.get("abstract") or "").lower().find(ql) >= 0
                        or (item.get("authors") or "").lower().find(ql) >= 0
                    )
                batch_items = [it for it in batch_items if _match(it)]
            if category and category.strip():
                cl = category.strip().lower()
                batch_items = [it for it in batch_items if (item := (it.get("category") or "").lower()) == cl or item.replace(" ", "_") == cl]

            collected.extend(batch_items)
            if len(batch_items) < BATCH:
                # End reached (returned fewer than BATCH entries)
                break
            cursor += BATCH
            batches += 1

        # Now slice according to within-batch offset and limit
        page_items = collected[within_batch_offset:within_batch_offset + limit]
        return page_items, (len(collected) if query or category else total), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to BioRxiv API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to BioRxiv API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"BioRxiv API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"BioRxiv API Request Error: {str(e)}"
        return None, 0, f"Unexpected error during BioRxiv search: {str(e)}"


def get_biorxiv_by_doi(
    doi: str,
    server: str = "biorxiv",
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Fetch a single manuscript by DOI via /details/{server}/{DOI}/na.

    Returns (item_dict, error_message). item_dict is normalized to BioRxivPaper shape.
    """
    try:
        if not doi or not doi.strip():
            return None, "DOI cannot be empty"
        server_norm = server.lower().strip() if server else "biorxiv"
        if server_norm not in {"biorxiv", "medrxiv"}:
            server_norm = "biorxiv"
        session = _mk_session()
        doi_enc = requests.utils.quote(doi.strip(), safe="/")  # keep slashes within DOI
        url = f"{BIO_RXIV_API_BASE}/details/{server_norm}/{doi_enc}/na"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        coll = data.get("collection") or []
        if not coll:
            return None, None
        # Take the first item
        item = _normalize_item(coll[0])
        return item, None
    except requests.exceptions.Timeout:
        return None, "Request to BioRxiv API timed out."
    except requests.exceptions.HTTPError as e:
        return None, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
    except requests.exceptions.RequestException as e:
        return None, f"BioRxiv API Request Error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error during BioRxiv DOI lookup: {str(e)}"



# End of BioRxiv.py

def search_biorxiv_pubs(
    server: str = "biorxiv",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
    recent_days: Optional[int] = None,
    recent_count: Optional[int] = None,
    q: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    """Search published article details via /pubs endpoint (bioRxiv/medRxiv)."""
    try:
        server_norm = server.lower().strip() if server else "biorxiv"
        if server_norm not in {"biorxiv", "medrxiv"}:
            server_norm = "biorxiv"

        f = _validate_date(from_date)
        t = _validate_date(to_date)
        if not (f and t) and not (recent_days or recent_count):
            f, t = _default_date_range()

        BATCH = 100
        first_cursor = (offset // BATCH) * BATCH
        within_batch_offset = offset - first_cursor

        session = _mk_session()

        def _interval_path(cursor: int) -> str:
            if recent_days and recent_days > 0:
                interval = f"{recent_days}d"
                return f"/pubs/{server_norm}/{interval}/{cursor}"
            if recent_count and recent_count > 0:
                interval = str(recent_count)
                return f"/pubs/{server_norm}/{interval}/{cursor}"
            return f"/pubs/{server_norm}/{f}/{t}/{cursor}"

        def _fetch(cursor: int) -> Tuple[List[Dict[str, Any]], int]:
            url = f"{BIO_RXIV_API_BASE}{_interval_path(cursor)}"
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            cnt = 0
            msgs = data.get("messages") or []
            if isinstance(msgs, list) and msgs:
                try:
                    cnt = int((msgs[0].get("count") or 0))
                except Exception:
                    cnt = 0
            coll = [_normalize_published_item(it) for it in (data.get("collection") or [])]
            time.sleep(0.2)
            return coll, cnt

        collected: List[Dict[str, Any]] = []
        cursor = first_cursor
        batches = 0
        max_batches = 5
        total_count = 0
        while batches < max_batches and len(collected) < (within_batch_offset + limit):
            items, cnt = _fetch(cursor)
            if total_count == 0:
                total_count = cnt
            if q and q.strip():
                ql = q.strip().lower()
                items = [it for it in items if (it.get("preprint_title") or "").lower().find(ql) >= 0 or (it.get("preprint_abstract") or "").lower().find(ql) >= 0 or (it.get("preprint_authors") or "").lower().find(ql) >= 0]
            collected.extend(items)
            if len(items) < BATCH:
                break
            cursor += BATCH
            batches += 1

        page_items = collected[within_batch_offset:within_batch_offset + limit]
        return page_items, (len(collected) if q else total_count), None
    except requests.exceptions.Timeout:
        return None, 0, "Request to BioRxiv API timed out."
    except requests.exceptions.HTTPError as e:
        return None, 0, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
    except requests.exceptions.RequestException as e:
        return None, 0, f"BioRxiv API Request Error: {str(e)}"
    except Exception as e:
        return None, 0, f"Unexpected error during BioRxiv pubs search: {str(e)}"


def get_biorxiv_published_by_doi(
    doi: str,
    server: str = "biorxiv",
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Fetch published metadata by DOI via /pubs/{server}/{DOI}/na."""
    try:
        if not doi or not doi.strip():
            return None, "DOI cannot be empty"
        server_norm = server.lower().strip() if server else "biorxiv"
        if server_norm not in {"biorxiv", "medrxiv"}:
            server_norm = "biorxiv"
        session = _mk_session()
        doi_enc = requests.utils.quote(doi.strip(), safe="/")
        url = f"{BIO_RXIV_API_BASE}/pubs/{server_norm}/{doi_enc}/na"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        coll = data.get("collection") or []
        if not coll:
            return None, None
        return _normalize_published_item(coll[0]), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to BioRxiv API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to BioRxiv API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"BioRxiv API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"BioRxiv API Request Error: {str(e)}"
        return None, f"Unexpected error during BioRxiv published DOI lookup: {str(e)}"


# ---------------- Additional Reports Endpoints ----------------

def search_biorxiv_publisher(
    publisher_prefix: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
    recent_days: Optional[int] = None,
    recent_count: Optional[int] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    """Search by publisher prefix via /publisher/{prefix}/{interval}/{cursor} (bioRxiv only)."""
    try:
        if not publisher_prefix or not publisher_prefix.strip():
            return None, 0, "publisher_prefix is required"
        f = _validate_date(from_date)
        t = _validate_date(to_date)
        # Default to last 30 days if nothing provided
        if not (f and t) and not (recent_days or recent_count):
            f, t = _default_date_range()

        BATCH = 100
        first_cursor = (offset // BATCH) * BATCH
        within_batch_offset = offset - first_cursor
        session = _mk_session()

        def _interval_path(cursor: int) -> str:
            if recent_days and recent_days > 0:
                interval = f"{recent_days}d"
                return f"/publisher/{publisher_prefix}/{interval}/{cursor}"
            if recent_count and recent_count > 0:
                interval = str(recent_count)
                return f"/publisher/{publisher_prefix}/{interval}/{cursor}"
            return f"/publisher/{publisher_prefix}/{f}/{t}/{cursor}"

        def _fetch(cursor: int) -> Tuple[List[Dict[str, Any]], int]:
            url = f"{BIO_RXIV_API_BASE}{_interval_path(cursor)}"
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            cnt = 0
            msgs = data.get("messages") or []
            if isinstance(msgs, list) and msgs:
                try:
                    cnt = int((msgs[0].get("count") or 0))
                except Exception:
                    cnt = 0
            coll = [_normalize_published_item(it) for it in (data.get("collection") or [])]
            time.sleep(0.2)
            return coll, cnt

        collected: List[Dict[str, Any]] = []
        cursor = first_cursor
        total_count = 0
        batches = 0
        max_batches = 5
        while batches < max_batches and len(collected) < (within_batch_offset + limit):
            items, cnt = _fetch(cursor)
            if total_count == 0:
                total_count = cnt
            collected.extend(items)
            if len(items) < BATCH:
                break
            cursor += BATCH
            batches += 1

        page_items = collected[within_batch_offset:within_batch_offset + limit]
        return page_items, total_count, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to BioRxiv API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to BioRxiv API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"BioRxiv API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"BioRxiv API Request Error: {str(e)}"
        return None, 0, f"Unexpected error during BioRxiv publisher search: {str(e)}"


def search_biorxiv_pub(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
    recent_days: Optional[int] = None,
    recent_count: Optional[int] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    """Published article detail via /pub endpoint (bioRxiv only)."""
    try:
        f = _validate_date(from_date)
        t = _validate_date(to_date)
        if not (f and t) and not (recent_days or recent_count):
            f, t = _default_date_range()

        BATCH = 100
        first_cursor = (offset // BATCH) * BATCH
        within_batch_offset = offset - first_cursor

        session = _mk_session()

        def _interval_path(cursor: int) -> str:
            if recent_days and recent_days > 0:
                return f"/pub/{recent_days}d/{cursor}"
            if recent_count and recent_count > 0:
                return f"/pub/{recent_count}/{cursor}"
            return f"/pub/{f}/{t}/{cursor}"

        def _fetch(cursor: int) -> Tuple[List[Dict[str, Any]], int]:
            url = f"{BIO_RXIV_API_BASE}{_interval_path(cursor)}"
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            cnt = 0
            msgs = data.get("messages") or []
            if isinstance(msgs, list) and msgs:
                try:
                    cnt = int((msgs[0].get("count") or 0))
                except Exception:
                    cnt = 0
            coll = [_normalize_published_item(it) for it in (data.get("collection") or [])]
            time.sleep(0.2)
            return coll, cnt

        collected: List[Dict[str, Any]] = []
        cursor = first_cursor
        batches = 0
        max_batches = 5
        total_count = 0
        while batches < max_batches and len(collected) < (within_batch_offset + limit):
            items, cnt = _fetch(cursor)
            if total_count == 0:
                total_count = cnt
            collected.extend(items)
            if len(items) < BATCH:
                break
            cursor += BATCH
            batches += 1

        page_items = collected[within_batch_offset:within_batch_offset + limit]
        return page_items, total_count, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to BioRxiv API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to BioRxiv API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"BioRxiv API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"BioRxiv API Request Error: {str(e)}"
        return None, 0, f"Unexpected error during BioRxiv pub search: {str(e)}"


def _normalize_funder_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    base = _normalize_item(raw)
    # Attach funder info best-effort
    base["funder"] = raw.get("funder")
    return base


def search_biorxiv_funder(
    server: str,
    ror_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    offset: int = 0,
    limit: int = 10,
    recent_days: Optional[int] = None,
    recent_count: Optional[int] = None,
    category: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    """Search /funder/{server}/{interval}/{ror_id}/{cursor} with optional category."""
    try:
        if not ror_id or not ror_id.strip():
            return None, 0, "ror_id is required"
        server_norm = (server or "biorxiv").lower()
        if server_norm not in {"biorxiv", "medrxiv"}:
            server_norm = "biorxiv"

        f = _validate_date(from_date)
        t = _validate_date(to_date)
        if not (f and t) and not (recent_days or recent_count):
            f, t = _default_date_range()

        BATCH = 100
        first_cursor = (offset // BATCH) * BATCH
        within_batch_offset = offset - first_cursor
        session = _mk_session()

        def _interval_path(cursor: int) -> str:
            if recent_days and recent_days > 0:
                return f"/funder/{server_norm}/{recent_days}d/{ror_id}/{cursor}"
            if recent_count and recent_count > 0:
                return f"/funder/{server_norm}/{recent_count}/{ror_id}/{cursor}"
            return f"/funder/{server_norm}/{f}/{t}/{ror_id}/{cursor}"

        def _fetch(cursor: int) -> Tuple[List[Dict[str, Any]], int]:
            url = f"{BIO_RXIV_API_BASE}{_interval_path(cursor)}"
            params = None
            if category and category.strip():
                cat_value = category.strip().replace(" ", "_")
                params = {"category": cat_value}
            resp = session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            cnt = 0
            msgs = data.get("messages") or []
            if isinstance(msgs, list) and msgs:
                try:
                    cnt = int((msgs[0].get("count") or 0))
                except Exception:
                    cnt = 0
            coll = [_normalize_funder_item(it) for it in (data.get("collection") or [])]
            time.sleep(0.2)
            return coll, cnt

        collected: List[Dict[str, Any]] = []
        cursor = first_cursor
        batches = 0
        max_batches = 5
        total_count = 0
        while batches < max_batches and len(collected) < (within_batch_offset + limit):
            items, cnt = _fetch(cursor)
            if total_count == 0:
                total_count = cnt
            collected.extend(items)
            if len(items) < BATCH:
                break
            cursor += BATCH
            batches += 1

        page_items = collected[within_batch_offset:within_batch_offset + limit]
        return page_items, total_count, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, 0, "Request to BioRxiv API timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, 0, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, 0, "Request to BioRxiv API timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, 0, f"BioRxiv API HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, 0, f"BioRxiv API Request Error: {str(e)}"
        return None, 0, f"Unexpected error during BioRxiv funder search: {str(e)}"


def get_biorxiv_summary(interval: str = "m") -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Content summary statistics via /sum/{interval}. interval: 'm' or 'y'."""
    try:
        iv = interval.lower().strip()
        if iv not in {"m", "y"}:
            iv = "m"
        session = _mk_session()
        url = f"{BIO_RXIV_API_BASE}/sum/{iv}"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json() or {}
        # Response contains keys like 'month', 'new_papers', etc. Usually wrapped inside 'summary' or direct list.
        # Standardize to list under 'items'
        if isinstance(data, dict) and "summary" in data:
            items = data.get("summary") or []
        else:
            items = data if isinstance(data, list) else []
        return items, None
    except requests.exceptions.Timeout:
        return None, "Request to BioRxiv API timed out."
    except requests.exceptions.HTTPError as e:
        return None, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
    except requests.exceptions.RequestException as e:
        return None, f"BioRxiv API Request Error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error during BioRxiv summary fetch: {str(e)}"


def get_biorxiv_usage(interval: str = "m") -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Usage statistics via /usage/{interval}. interval: 'm' or 'y'."""
    try:
        iv = interval.lower().strip()
        if iv not in {"m", "y"}:
            iv = "m"
        session = _mk_session()
        url = f"{BIO_RXIV_API_BASE}/usage/{iv}"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json() or {}
        if isinstance(data, dict) and "usage" in data:
            items = data.get("usage") or []
        else:
            items = data if isinstance(data, list) else []
        return items, None
    except requests.exceptions.Timeout:
        return None, "Request to BioRxiv API timed out."
    except requests.exceptions.HTTPError as e:
        return None, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
    except requests.exceptions.RequestException as e:
        return None, f"BioRxiv API Request Error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error during BioRxiv usage fetch: {str(e)}"


# ---------------- Raw passthrough helpers ----------------

def raw_details(
    server: str,
    from_date: Optional[str],
    to_date: Optional[str],
    recent_days: Optional[int],
    recent_count: Optional[int],
    doi: Optional[str],
    cursor: int = 0,
    category: Optional[str] = None,
    fmt: Optional[str] = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    server_norm = (server or "biorxiv").lower()
    if doi and doi.strip():
        doi_enc = requests.utils.quote(doi.strip(), safe="/")
        path = f"/details/{server_norm}/{doi_enc}/na"
        return _raw_get(path, fmt)
    f = _validate_date(from_date)
    t = _validate_date(to_date)
    if not (f and t):
        f, t = _default_date_range()
    if recent_days and recent_days > 0:
        interval = f"{recent_days}d"
    elif recent_count and recent_count > 0:
        interval = str(recent_count)
    else:
        interval = f"{f}/{t}"
    path = f"/details/{server_norm}/{interval}/{cursor}"
    params = None
    if category and category.strip():
        params = {"category": category.strip().replace(" ", "_")}
    return _raw_get(path, fmt, params)


def raw_pubs(
    server: str,
    from_date: Optional[str],
    to_date: Optional[str],
    recent_days: Optional[int],
    recent_count: Optional[int],
    doi: Optional[str],
    cursor: int = 0,
    fmt: Optional[str] = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    server_norm = (server or "biorxiv").lower()
    if doi and doi.strip():
        doi_enc = requests.utils.quote(doi.strip(), safe="/")
        path = f"/pubs/{server_norm}/{doi_enc}/na"
        return _raw_get(path, fmt)
    f = _validate_date(from_date)
    t = _validate_date(to_date)
    if not (f and t) and not (recent_days or recent_count):
        f, t = _default_date_range()
    if recent_days and recent_days > 0:
        interval = f"{recent_days}d"
    elif recent_count and recent_count > 0:
        interval = str(recent_count)
    else:
        interval = f"{f}/{t}"
    path = f"/pubs/{server_norm}/{interval}/{cursor}"
    return _raw_get(path, fmt)


def raw_pub(
    from_date: Optional[str],
    to_date: Optional[str],
    recent_days: Optional[int],
    recent_count: Optional[int],
    cursor: int = 0,
    fmt: Optional[str] = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    f = _validate_date(from_date)
    t = _validate_date(to_date)
    if not (f and t) and not (recent_days or recent_count):
        f, t = _default_date_range()
    if recent_days and recent_days > 0:
        interval = f"{recent_days}d"
    elif recent_count and recent_count > 0:
        interval = str(recent_count)
    else:
        interval = f"{f}/{t}"
    path = f"/pub/{interval}/{cursor}"
    return _raw_get(path, fmt)


def raw_funder(
    server: str,
    ror_id: str,
    from_date: Optional[str],
    to_date: Optional[str],
    recent_days: Optional[int],
    recent_count: Optional[int],
    cursor: int = 0,
    category: Optional[str] = None,
    fmt: Optional[str] = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    server_norm = (server or "biorxiv").lower()
    f = _validate_date(from_date)
    t = _validate_date(to_date)
    if not (f and t) and not (recent_days or recent_count):
        f, t = _default_date_range()
    if recent_days and recent_days > 0:
        interval = f"{recent_days}d"
    elif recent_count and recent_count > 0:
        interval = str(recent_count)
    else:
        interval = f"{f}/{t}"
    path = f"/funder/{server_norm}/{interval}/{ror_id}/{cursor}"
    params = None
    if category and category.strip():
        params = {"category": category.strip().replace(" ", "_")}
    return _raw_get(path, fmt, params)


def raw_sum(interval: str = "m", fmt: Optional[str] = None) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    iv = (interval or "m").lower()
    path = f"/sum/{iv}"
    return _raw_get(path, fmt)


def raw_usage(interval: str = "m", fmt: Optional[str] = None) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    iv = (interval or "m").lower()
    path = f"/usage/{iv}"
    return _raw_get(path, fmt)
