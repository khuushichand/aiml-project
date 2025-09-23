# BioRxiv.py
# Description: Functions to search BioRxiv/MedRxiv APIs with retries, timeouts, and
#              a normalized response shape used by paper-search endpoints.

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


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


def _mk_session() -> requests.Session:
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
    except requests.exceptions.Timeout:
        return None, 0, "Request to BioRxiv API timed out."
    except requests.exceptions.HTTPError as e:
        return None, 0, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
    except requests.exceptions.RequestException as e:
        return None, 0, f"BioRxiv API Request Error: {str(e)}"
    except Exception as e:
        return None, 0, f"Unexpected error during BioRxiv search: {str(e)}"


# End of BioRxiv.py
