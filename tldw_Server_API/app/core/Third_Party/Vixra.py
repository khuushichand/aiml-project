"""viXra.org minimal adapter.

Since viXra does not provide an official public REST API, we implement a
best-effort adapter for lookups by viXra identifier (e.g., '1901.0001').

Capabilities:
 - Given a viXra ID, attempt to locate a PDF link via common patterns:
     https://vixra.org/pdf/{id}.pdf
     https://vixra.org/pdf/{id}v{n}.pdf for n in 1..5
 - Fallback: fetch the abstract page https://vixra.org/abs/{id} and extract
   the PDF link via a simple regex.

Returns a GenericPaper-like dict with provider='vixra'. Title/authors are not
extracted unless trivially available; PDF ingest path uses the resolved pdf_url.
"""
from __future__ import annotations

from typing import Optional, Tuple, Dict, Any, List
import re
import requests
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tldw_Server_API.app.core.http_client import create_client


ABS_URL = "https://vixra.org/abs/{vid}"
PDF_BASE = "https://vixra.org/pdf/{suffix}"


def _mk_session():
    try:
        return create_client(timeout=20)
    except Exception:
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        s = requests.Session()
        s.headers.update({
            "Accept": "text/html,application/pdf,application/json",
            "User-Agent": "tldw_server/1.0 (+https://github.com/)",
        })
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s


def _try_pdf(session, url: str) -> Optional[str]:
    try:
        # httpx.Client supports allow_redirects on head as well
        r = session.head(url, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            ct = (r.headers.get("content-type") or "").lower()
            if "pdf" in ct or url.lower().endswith(".pdf"):
                return url
        return None
    except Exception:
        return None


def _extract_pdf_from_abs(session, abs_url: str) -> Optional[str]:
    try:
        r = session.get(abs_url, timeout=20)
        r.raise_for_status()
        text = r.text or ""
        m = re.search(r"href=\"(/pdf/[A-Za-z0-9\./v_-]+?\.pdf)\"", text, re.IGNORECASE)
        if m:
            href = m.group(1)
            if href.startswith("/"):
                return f"https://vixra.org{href}"
        return None
    except Exception:
        return None


def get_vixra_by_id(vid: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Resolve a viXra ID to a PDF URL and minimal metadata."""
    try:
        vid = (vid or "").strip()
        if not vid:
            return None, "Invalid viXra ID"
        session = _mk_session()

        # Try common PDF patterns
        candidates = [PDF_BASE.format(suffix=f"{vid}.pdf")]
        for n in range(1, 6):
            candidates.append(PDF_BASE.format(suffix=f"{vid}v{n}.pdf"))
        pdf_url = None
        for url in candidates:
            pdf_url = _try_pdf(session, url)
            if pdf_url:
                break
        # Fetch abstract page for metadata enrichment and PDF fallback
        abs_url = ABS_URL.format(vid=vid)
        html = None
        try:
            r_abs = session.get(abs_url, timeout=20)
            if r_abs.status_code == 200:
                html = r_abs.text or None
        except requests.RequestException:
            html = None

        if not pdf_url:
            pdf_url = _extract_pdf_from_abs(session, abs_url)

        title = None
        authors = None
        pub_date = None
        if html:
            title, authors, pub_date = _parse_abs_details(html)

        item = {
            "id": vid,
            "title": title,
            "authors": authors,
            "journal": None,
            "pub_date": pub_date,
            "abstract": None,
            "doi": None,
            "url": abs_url,
            "pdf_url": pdf_url,
            "provider": "vixra",
        }
        return item, None
    except Exception as e:
        return None, f"vixra error: {str(e)}"


def search(term: str, page: int = 1, results_per_page: int = 10) -> Tuple[Optional[List[Dict[str, Any]]], int, Optional[str]]:
    """Best-effort viXra search by term, scraping HTML for /abs/ links.

    Returns (items, total_estimate, error). We do not attempt strong pagination.
    """
    try:
        if not term or not term.strip():
            return [], 0, None
        session = _mk_session()
        q = term.strip()
        # Candidate search endpoints observed historically
        candidates = [
            f"https://vixra.org/find/?search={requests.utils.quote(q)}",
            f"https://vixra.org/?search={requests.utils.quote(q)}",
            f"https://vixra.org/?find={requests.utils.quote(q)}",
        ]
        html = None
        url_used = None
        for url in candidates:
            try:
                r = session.get(url, timeout=20)
                if r.status_code == 200 and r.text:
                    html = r.text
                    url_used = url
                    break
            except requests.RequestException:
                continue
        if not html:
            return [], 0, "viXra search failed to fetch results"

        # Parse /abs/ links with titles
        # Look for anchors like <a href="/abs/1901.0001">Title...</a>
        items: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(r"<a[^>]+href=\"(/abs/[A-Za-z0-9\.v/_-]+)\"[^>]*>(.*?)</a>", html, re.IGNORECASE | re.DOTALL):
            href = m.group(1)
            raw_title = m.group(2) or ""
            # Clean title (strip tags & whitespace)
            title = re.sub(r"<[^>]+>", " ", raw_title)
            title = re.sub(r"\s+", " ", title).strip()
            vid = href.split('/abs/')[-1]
            if not vid or vid in seen:
                continue
            seen.add(vid)
            # Enrich from abstract page for authors (and better title if available)
            abs_url = f"https://vixra.org/abs/{vid}"
            authors = None
            better_title = None
            pub_date = None
            try:
                r_abs = session.get(abs_url, timeout=12)
                if r_abs.status_code == 200 and r_abs.text:
                    better_title, authors, pub_date = _parse_abs_details(r_abs.text)
            except requests.RequestException:
                pass
            item = {
                "id": vid,
                "title": (better_title or title or None),
                "authors": authors,
                "journal": None,
                "pub_date": pub_date,
                "abstract": None,
                "doi": None,
                "url": abs_url,
                "pdf_url": None,  # leave null; ingest will resolve
                "provider": "vixra",
            }
            items.append(item)
            if len(items) >= results_per_page:
                break
        total = len(items)
        return items, total, None
    except Exception as e:
        return None, 0, f"vixra search error: {str(e)}"


def _parse_abs_details(html: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract title, authors, and date from viXra abstract HTML.

    Best-effort: try citation meta tags first; fall back to headings/text patterns.
    """
    try:
        title = None
        authors_list: List[str] = []
        pub_date = None

        # Meta tags
        for m in re.finditer(r'<meta\s+name=\"citation_title\"\s+content=\"([^\"]+)\"', html, re.IGNORECASE):
            title = m.group(1).strip()
            break
        for m in re.finditer(r'<meta\s+name=\"citation_author\"\s+content=\"([^\"]+)\"', html, re.IGNORECASE):
            nm = m.group(1).strip()
            if nm:
                authors_list.append(nm)
        for m in re.finditer(r'<meta\s+name=\"citation_date\"\s+content=\"([^\"]+)\"', html, re.IGNORECASE):
            pub_date = m.group(1).strip()
            break

        # Headings fallback for title
        if not title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
            if not m:
                m = re.search(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)
            if m:
                t = re.sub(r"<[^>]+>", " ", m.group(1))
                title = re.sub(r"\s+", " ", t).strip() or None

        # Authors fallback: look for 'Authors:' or 'Author:' line
        if not authors_list:
            m = re.search(r'(?:Authors?|authors?)\s*:\s*([^<\n]+)', html, re.IGNORECASE)
            if m:
                raw = m.group(1)
                # Split by comma or ' and '
                parts = re.split(r',|\band\b', raw)
                authors_list = [p.strip() for p in parts if p and p.strip()]
        if not authors_list:
            # Try "by <names>"
            m = re.search(r'>\s*by\s+([^<\n]+)<', html, re.IGNORECASE)
            if m:
                raw = m.group(1)
                parts = re.split(r',|\band\b', raw)
                authors_list = [p.strip() for p in parts if p and p.strip()]

        authors = ", ".join(authors_list) if authors_list else None
        return title, authors, pub_date
    except Exception:
        return None, None, None
