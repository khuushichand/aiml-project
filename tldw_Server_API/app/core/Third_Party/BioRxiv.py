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

        def _fetch(cursor: int) -> Tuple[List[Dict[str, Any]], int]:
            # As of current API behavior, rely on /details and apply keyword/category filters client-side
            # /details/{server}/{from}/{to}/{cursor}
            path = f"/details/{server_norm}/{f}/{t}/{cursor}"
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
            # Apply client-side filters
            if query and query.strip():
                ql = query.strip().lower()
                def _match(item: Dict[str, Any]) -> bool:
                    return (
                        (item.get("title") or "").lower().find(ql) >= 0
                        or (item.get("abstract") or "").lower().find(ql) >= 0
                        or (item.get("authors") or "").lower().find(ql) >= 0
                    )
                batch_items = [it for it in batch_items if _match(it)]

            collected.extend(batch_items)
            if len(batch_items) < BATCH:
                # End reached (returned fewer than BATCH entries)
                break
            cursor += BATCH
            batches += 1

        # Now slice according to within-batch offset and limit
        page_items = collected[within_batch_offset:within_batch_offset + limit]
        return page_items, (len(collected) if query or category else total), None
    except requests.exceptions.Timeout:
        return None, 0, "Request to BioRxiv API timed out."
    except requests.exceptions.HTTPError as e:
        return None, 0, f"BioRxiv API HTTP Error: {getattr(e.response, 'status_code', '?')}"
    except requests.exceptions.RequestException as e:
        return None, 0, f"BioRxiv API Request Error: {str(e)}"
    except Exception as e:
        return None, 0, f"Unexpected error during BioRxiv search: {str(e)}"


# End of BioRxiv.py
