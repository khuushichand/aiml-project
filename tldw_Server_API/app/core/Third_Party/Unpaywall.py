"""Unpaywall client for OA PDF resolution by DOI.

Requires contact email via `UNPAYWALL_EMAIL`.
Returns (pdf_url, error_message).
"""
from __future__ import annotations

import os
from typing import Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://api.unpaywall.org/v2"


def _mk_session() -> requests.Session:
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    s = requests.Session()
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def resolve_oa_pdf(doi: str) -> Tuple[Optional[str], Optional[str]]:
    """Resolve an OA PDF URL for the given DOI using Unpaywall.

    Returns (pdf_url, error_message). Missing email -> error; 404 -> (None, None).
    """
    email = os.getenv("UNPAYWALL_EMAIL")
    if not email:
        return None, "Unpaywall contact email not configured. Set UNPAYWALL_EMAIL."
    try:
        session = _mk_session()
        doi_clean = doi.strip()
        url = f"{BASE_URL}/{doi_clean}"
        r = session.get(url, params={"email": email}, timeout=20)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json() or {}
        # Prefer best_oa_location.url_for_pdf, then scan oa_locations
        best = data.get("best_oa_location") or {}
        pdf = best.get("url_for_pdf") or best.get("url")
        if not pdf:
            for loc in data.get("oa_locations") or []:
                pdf = loc.get("url_for_pdf") or loc.get("url")
                if pdf:
                    break
        return (pdf if pdf else None), None
    except requests.exceptions.Timeout:
        return None, "Request to Unpaywall API timed out."
    except requests.exceptions.HTTPError as e:
        return None, f"Unpaywall API HTTP Error: {getattr(e.response, 'status_code', '?')}"
    except requests.exceptions.RequestException as e:
        return None, f"Unpaywall API Request Error: {str(e)}"
    except Exception as e:
        return None, f"Unpaywall error: {str(e)}"
