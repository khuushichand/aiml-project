"""
Watchlists fetch helpers for RSS/Atom feeds and HTML scraping.

Highlights:
- RSS fetch: reuses workflows adapter logic for URL policy checks and XML parsing.
  TEST_MODE returns static items so offline unit tests stay deterministic.
- Site fetch: relies on the blocking article extractor plus optional rule-based
  list scraping informed by FreshRSS-style XPath/CSS selectors.

Returned item structure (normalized):
- RSS items: { 'title': str, 'url': str, 'summary': Optional[str], 'published': Optional[str] }
- Site articles: { 'title': str, 'url': str, 'content': str, 'author': Optional[str] }
- Scraped list items: { 'title': str, 'url': str, 'summary': Optional[str], 'content': Optional[str], ... }
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urljoin

import httpx
import xml.etree.ElementTree as ET
from loguru import logger
from lxml import html
from lxml.etree import XPathError
from lxml.html import HtmlElement

from tldw_Server_API.app.core.Security.egress import is_url_allowed_for_tenant, is_url_allowed

_TEST_MODE_VALUES = {"1", "true", "yes"}


def _in_test_mode() -> bool:
    return os.getenv("TEST_MODE", "").lower() in _TEST_MODE_VALUES


def _ensure_sequence(value: Sequence[str] | str | None) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if isinstance(v, str)]


def _select_nodes(node: HtmlElement, selector: str) -> List[Any]:
    expr = selector.strip()
    if not expr:
        return []
    if expr.startswith("css:"):
        css_expr = expr[4:].strip()
        if not css_expr:
            return []
        try:
            from lxml.cssselect import CSSSelector
        except Exception as exc:
            logger.debug(f"CSS selector support unavailable for '{css_expr}': {exc}")
            return []
        try:
            sel = CSSSelector(css_expr)
            return list(sel(node))
        except Exception as exc:
            logger.debug(f"CSS selector evaluation failed for '{css_expr}': {exc}")
            return []
    try:
        result = node.xpath(expr)
    except XPathError as exc:
        logger.debug(f"XPath evaluation failed for '{expr}': {exc}")
        return []
    if isinstance(result, list):
        return result
    return [result]


def _coerce_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", errors="ignore").strip()
            return text or None
        except Exception:
            return None
    if hasattr(value, "text_content"):
        try:
            text = value.text_content().strip()
            return text or None
        except Exception:
            return None
    try:
        text = str(value).strip()
        return text or None
    except Exception:
        return None


def _reduce_matches(matches: Sequence[Any], join_with: str) -> Optional[str]:
    parts: List[str] = []
    for match in matches:
        val = _coerce_value(match)
        if val:
            parts.append(val)
    if not parts:
        return None
    return join_with.join(parts).strip() or None


def _extract_value(
    node: HtmlElement,
    selectors: Sequence[str] | str | None,
    *,
    join: bool = False,
    join_with: str = " ",
) -> Optional[str]:
    for expr in _ensure_sequence(selectors):
        matches = _select_nodes(node, expr)
        if not matches:
            continue
        if join:
            value = _reduce_matches(matches, join_with)
        else:
            value = _coerce_value(matches[0])
        if value:
            return value
    return None


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _normalize_datetime(raw: str, fmt: Optional[str] = None) -> Optional[str]:
    text = (raw or "").strip()
    if not text:
        return None
    if fmt:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            pass
    # Try dateutil if available
    try:
        from dateutil import parser as dateutil_parser  # type: ignore

        dt = dateutil_parser.parse(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    # Fallback to email.utils
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(text)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    return text


def parse_scraped_items(html_text: str, base_url: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    """Parse HTML into structured items using XPath/CSS rules.

    Returns dict: { "items": [...], "next_pages": [...] } to support pagination-aware callers.
    """
    result: Dict[str, Any] = {"items": [], "next_pages": []}
    if not html_text:
        return result
    try:
        document = html.fromstring(html_text)
    except Exception as exc:
        logger.debug(f"parse_scraped_items HTML parse failed: {exc}")
        return result

    try:
        document.make_links_absolute(base_url)
    except Exception:
        pass

    def _gather_items(rule_set: Dict[str, Any], *, seen: set[str], items: List[Dict[str, Any]], limit: Optional[int]) -> None:
        entry_selectors = (
            rule_set.get("entry_xpath")
            or rule_set.get("item_xpath")
            or rule_set.get("items_xpath")
            or rule_set.get("entry_selector")
            or rule_set.get("item_selector")
            or rules.get("entry_xpath")
            or rules.get("item_xpath")
            or rules.get("items_xpath")
            or rules.get("entry_selector")
            or rules.get("item_selector")
        )
        nodes: List[HtmlElement] = []
        for selector in _ensure_sequence(entry_selectors) or ["//article", "//item"]:
            nodes.extend([n for n in _select_nodes(document, selector) if isinstance(n, HtmlElement)])
        if not nodes:
            nodes = [document]

        summary_join = str(rule_set.get("summary_join_with") or rules.get("summary_join_with") or " ")
        content_join = str(rule_set.get("content_join_with") or rules.get("content_join_with") or "\n")

        for node in nodes:
            link = _extract_value(
                node,
                rule_set.get("link_xpath")
                or rule_set.get("url_xpath")
                or rules.get("link_xpath")
                or rules.get("url_xpath"),
                join=False,
            )
            if not link:
                continue
            link = link.strip()
            if not link or link in seen:
                continue
            seen.add(link)

            item: Dict[str, Any] = {"url": link}
            title = _extract_value(
                node,
                rule_set.get("title_xpath") or rule_set.get("title_selector") or rules.get("title_xpath") or rules.get("title_selector"),
                join=False,
            )
            if title:
                item["title"] = title
            summary = _extract_value(
                node,
                rule_set.get("summary_xpath")
                or rule_set.get("description_xpath")
                or rule_set.get("summary_selector")
                or rules.get("summary_xpath")
                or rules.get("description_xpath")
                or rules.get("summary_selector"),
                join=True,
                join_with=summary_join,
            )
            if summary:
                item["summary"] = summary
            content = _extract_value(
                node,
                rule_set.get("content_xpath")
                or rule_set.get("content_selector")
                or rules.get("content_xpath")
                or rules.get("content_selector"),
                join=True,
                join_with=content_join,
            )
            if content:
                item["content"] = content
            author = _extract_value(
                node,
                rule_set.get("author_xpath") or rule_set.get("author_selector") or rules.get("author_xpath") or rules.get("author_selector"),
                join=False,
            )
            if author:
                item["author"] = author
            guid = _extract_value(
                node,
                rule_set.get("guid_xpath") or rule_set.get("id_xpath") or rules.get("guid_xpath") or rules.get("id_xpath"),
                join=False,
            )
            if guid:
                item["guid"] = guid
            published_raw = _extract_value(
                node,
                rule_set.get("published_xpath")
                or rule_set.get("date_xpath")
                or rule_set.get("date_selector")
                or rules.get("published_xpath")
                or rules.get("date_xpath")
                or rules.get("date_selector"),
                join=False,
            )
            if published_raw:
                item["published_raw"] = published_raw
                fmt = rule_set.get("published_format") or rules.get("published_format") or rule_set.get("date_format") or rules.get("date_format")
                parsed = _normalize_datetime(published_raw, fmt if isinstance(fmt, str) else None)
                if parsed:
                    item["published"] = parsed

            items.append(item)
            if limit is not None and len(items) >= limit:
                break
        return

    limit = _coerce_int(rules.get("limit") or rules.get("max_items"))
    items: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    _gather_items(rules, seen=seen_urls, items=items, limit=limit)

    alternates = rules.get("alternates")
    if isinstance(alternates, list):
        for alt in alternates:
            if not isinstance(alt, dict):
                continue
            if limit is not None and len(items) >= limit:
                break
            merged = {**rules, **alt}
            _gather_items(merged, seen=seen_urls, items=items, limit=limit)
            if limit is not None and len(items) >= limit:
                break

    pagination_cfg = rules.get("pagination") if isinstance(rules.get("pagination"), dict) else None
    next_pages: List[str] = []
    if pagination_cfg:
        candidate_selectors = _ensure_sequence(
            pagination_cfg.get("next_xpath")
            or pagination_cfg.get("next_selector")
            or pagination_cfg.get("next_link_xpath")
            or pagination_cfg.get("next_link_selector")
        )
        attr = pagination_cfg.get("next_attribute") or "href"
        for selector in candidate_selectors:
            matches = _select_nodes(document, selector)
            for match in matches:
                url = None
                if isinstance(match, HtmlElement):
                    url = match.get(attr)
                    if not url:
                        url = _coerce_value(match)
                else:
                    url = _coerce_value(match)
                if not url:
                    continue
                absolute = urljoin(base_url, url)
                if absolute not in next_pages:
                    next_pages.append(absolute)
    result["items"] = items
    result["next_pages"] = next_pages
    return result


async def fetch_rss_items(urls: List[str], *, limit: int = 10, tenant_id: str = "default") -> List[Dict[str, Any]]:
    """Fetch RSS/Atom feed items for the given URLs.

    Uses the workflows adapter implementation for consistency with URL
    allowlisting and parsing heuristics. In TEST_MODE, returns a single fake
    item to keep tests offline.
    """
    urls = [u for u in (urls or []) if isinstance(u, str) and u.strip()]
    if not urls:
        return []

    # Offline mode for unit tests
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        return [{"title": "Test Item", "url": "https://example.com/x", "summary": "Test", "published": None}][:limit]

    try:
        from tldw_Server_API.app.core.Workflows.adapters import run_rss_fetch_adapter  # reuse existing parser
        cfg = {"urls": urls, "limit": limit, "include_content": True}
        ctx = {"tenant_id": tenant_id}
        res = await run_rss_fetch_adapter(cfg, ctx)
        items = []
        for r in (res.get("results") or []):
            items.append({
                "title": r.get("title") or "",
                "url": r.get("link") or r.get("url") or "",
                "summary": r.get("summary"),
                "published": r.get("published"),
                "guid": r.get("guid"),
            })
        return items[:limit]
    except Exception as e:
        logger.warning(f"fetch_rss_items failed: {e}")
        return []


def fetch_site_article(url: str) -> Optional[Dict[str, Any]]:
    """Fetch and extract a single site article.

    Uses the blocking path from Article_Extractor, which works without a
    Playwright runtime. Returns None on failure.
    """
    try:
        from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
            scrape_article_blocking,
            ContentMetadataHandler,  # type: ignore
        )
    except Exception as e:
        logger.error(f"Article extractor import failed: {e}")
        return None

    try:
        data = scrape_article_blocking(url)
        if not data:
            return None
        # Normalize
        title = data.get("title") or "Untitled"
        author = data.get("author") or None
        content = data.get("content") or ""
        try:
            content = ContentMetadataHandler.strip_metadata(content)  # type: ignore[attr-defined]
        except Exception:
            pass
        return {"title": title, "url": url, "content": content, "author": author}
    except Exception as e:
        logger.warning(f"fetch_site_article failed for {url}: {e}")
        return None


async def fetch_site_top_links(base_url: str, *, top_n: int = 10, method: str = "frontpage") -> List[str]:
    """Discover top-N content links from a site.

    - method="frontpage": fetch homepage and extract likely-article links
    - method="sitemap": try EnhancedWebScraper.scrape_sitemap to pull URLs only

    Returns a list of URLs (same-origin) deduplicated, up to top_n.
    TEST_MODE: returns [base_url] repeated to satisfy callers without network.
    """
    if top_n <= 0:
        return []

    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        # Provide stable deterministic links
        return [base_url] * min(top_n, 3)

    # Try using EnhancedWebScraper when available
    try:
        from urllib.parse import urlparse, urljoin
        from bs4 import BeautifulSoup
        import aiohttp
        from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper
        from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import is_content_page

        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        # Auto-detect sitemap via robots.txt or common path when method='auto'
        async def _detect_sitemap(u: str) -> Optional[str]:
            try:
                import re
                timeout = aiohttp.ClientTimeout(total=6)
                robots_url = urljoin(origin, "/robots.txt")
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get(robots_url) as resp:
                        if resp.status // 100 == 2:
                            txt = await resp.text()
                            # Look for Sitemap lines
                            for line in txt.splitlines():
                                if line.lower().startswith("sitemap:"):
                                    sitemap_url = line.split(":", 1)[1].strip()
                                    return sitemap_url
                # Try common location
                common = urljoin(origin, "/sitemap.xml")
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get(common) as resp:
                        if resp.status // 100 == 2:
                            return common
            except Exception:
                return None
            return None

        effective_method = method or "auto"
        sitemap_url_for_auto: Optional[str] = None
        if effective_method == "auto":
            sitemap_url_for_auto = await _detect_sitemap(base_url)
            if sitemap_url_for_auto:
                effective_method = "sitemap"
            else:
                effective_method = "frontpage"

        # Sitemap method
        if effective_method == "sitemap" or base_url.endswith(".xml") or "sitemap" in base_url:
            scraper = EnhancedWebScraper()
            # We only need URLs; call scrape_sitemap then pluck the url fields
            sitemap_to_use = sitemap_url_for_auto or base_url
            results = await scraper.scrape_sitemap(sitemap_to_use, filter_func=is_content_page, max_urls=top_n)
            urls = []
            for r in results:
                u = r.get("url") or r.get("source_url")
                if not u:
                    continue
                if urlparse(u).netloc == parsed.netloc:
                    urls.append(u)
            # Dedup while preserving order
            seen = set()
            uniq = []
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    uniq.append(u)
            return uniq[:top_n]

        # Frontpage method: fetch HTML and pull article-like links
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(base_url) as resp:
                if resp.status // 100 != 2:
                    return [base_url]
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        for a in soup.find_all("a"):
            href = a.get("href")
            if not href:
                continue
            href = urljoin(origin, href)
            # Same origin and looks like content
            try:
                if urlparse(href).netloc != parsed.netloc:
                    continue
                if not is_content_page(href):
                    continue
            except Exception:
                continue
            links.append(href)
        # Dedup preserve order
        seen = set()
        uniq = []
        for u in links:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq[:top_n] if uniq else [base_url]
    except Exception as e:
        logger.debug(f"fetch_site_top_links fallback: {e}")
        return [base_url]


async def fetch_site_items_with_rules(
    base_url: str,
    rules: Dict[str, Any],
    *,
    tenant_id: str = "default",
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """Fetch a list page and extract items using scrape rules."""
    list_url = str(rules.get("list_url") or base_url or "").strip()
    if not list_url:
        return []

    limit = _coerce_int(rules.get("limit") or rules.get("max_items"), default=10)
    if limit is not None and limit < 0:
        limit = 0
    if limit == 0:
        return []

    pagination_cfg = rules.get("pagination") if isinstance(rules.get("pagination"), dict) else {}
    max_pages = _coerce_int(pagination_cfg.get("max_pages"), default=1)
    if max_pages is None or max_pages < 1:
        max_pages = 1

    if _in_test_mode():
        max_items = limit if limit is not None else 3
        max_items = min(max_items, 5)
        samples: List[Dict[str, Any]] = []
        for idx in range(max_items):
            url = f"{list_url.rstrip('/')}/test-scrape-{idx + 1}"
            samples.append(
                {
                    "title": f"Test scraped item {idx + 1}",
                    "url": url,
                    "summary": "Test summary from scrape rules.",
                    "content": "Test content from scrape rules.",
                }
            )
        return samples

    headers = {
        "User-Agent": "tldw-watchlist/0.1 (+https://github.com/your-org/tldw_server2)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }

    queue: List[str] = [list_url]
    visited: set[str] = set()
    seen_items: set[str] = set()
    collected: List[Dict[str, Any]] = []

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            while queue and len(visited) < max_pages:
                page_url = queue.pop(0)
                if page_url in visited:
                    continue
                visited.add(page_url)

                allowed = False
                try:
                    allowed = is_url_allowed_for_tenant(page_url, tenant_id)
                except Exception:
                    allowed = is_url_allowed(page_url)
                if not allowed:
                    logger.debug(f"Scrape rules blocked by URL policy: {page_url}")
                    continue

                try:
                    resp = client.get(page_url, headers=headers)
                except Exception as exc:
                    logger.debug(f"fetch_site_items_with_rules request failed ({page_url}): {exc}")
                    continue

                if resp.status_code // 100 != 2:
                    logger.debug(f"fetch_site_items_with_rules HTTP {resp.status_code} for {page_url}")
                    continue

                parsed = parse_scraped_items(resp.text or "", page_url, rules)
                page_items = parsed.get("items") or []
                for item in page_items:
                    url = item.get("url")
                    if not url or url in seen_items:
                        continue
                    seen_items.add(url)
                    collected.append(item)
                    if limit is not None and len(collected) >= limit:
                        break
                if limit is not None and len(collected) >= limit:
                    break

                next_pages = parsed.get("next_pages") or []
                for nxt in next_pages:
                    if not nxt or nxt in visited or nxt in queue:
                        continue
                    if len(visited) + len(queue) >= max_pages:
                        break
                    queue.append(nxt)
    except Exception as exc:
        logger.debug(f"fetch_site_items_with_rules pagination failed: {exc}")

    if limit is not None:
        return collected[:limit]
    return collected


async def fetch_rss_feed(
    url: str,
    *,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
    timeout: float = 8.0,
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """Fetch a single RSS/Atom feed with conditional headers.

    Returns dict:
      - status: int HTTP code (200/304/429/other)
      - items: list[dict] when 200
      - etag: str|None (from response headers)
      - last_modified: str|None (from response headers)
      - retry_after: int seconds (only when 429 and header present)
    """
    try:
        if not (url.startswith("http://") or url.startswith("https://")):
            return {"status": 400, "items": []}
        allowed = False
        try:
            allowed = is_url_allowed_for_tenant(url, tenant_id)
        except Exception:
            allowed = is_url_allowed(url)
        if not allowed:
            return {"status": 403, "items": []}

        headers = {
            "Accept": "application/atom+xml, application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": "tldw-watchlist/0.1 (+https://github.com/your-org/tldw_server2)"
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)

        status = int(resp.status_code)
        # Retry-After handling
        if status == 429:
            ra = resp.headers.get("Retry-After")
            retry_after_secs = None
            if ra:
                ra = ra.strip()
                # Seconds or HTTP-date
                try:
                    retry_after_secs = int(ra)
                except Exception:
                    from email.utils import parsedate_to_datetime
                    try:
                        dt = parsedate_to_datetime(ra)
                        import datetime as _dt
                        retry_after_secs = max(0, int((dt - _dt.datetime.utcnow().replace(tzinfo=dt.tzinfo)).total_seconds()))
                    except Exception:
                        retry_after_secs = None
            return {"status": 429, "items": [], "retry_after": retry_after_secs}

        if status == 304:
            return {
                "status": 304,
                "items": [],
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
            }

        if status // 100 != 2:
            return {"status": status, "items": []}

        text = resp.text
        try:
            root = ET.fromstring(text)
        except Exception:
            return {
                "status": status,
                "items": [],
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
            }

        def _find_text(node, names):
            for n in names:
                x = node.find(n)
                if x is not None and (x.text or "").strip():
                    return x.text.strip()
            return None

        items_nodes = root.findall('.//item')
        if not items_nodes:
            items_nodes = root.findall('.//{http://www.w3.org/2005/Atom}entry')
        items: List[Dict[str, Any]] = []
        for it in items_nodes:
            title = _find_text(it, ["title", "{http://www.w3.org/2005/Atom}title"]) or ""
            link = None
            lnode = it.find("link")
            if lnode is not None and (lnk := lnode.get("href")):
                link = lnk
            else:
                link = _find_text(it, ["link", "{http://www.w3.org/2005/Atom}link"]) or ""
            summary = _find_text(it, ["description", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"]) or ""
            published = _find_text(it, ["pubDate", "{http://www.w3.org/2005/Atom}updated", "{http://www.w3.org/2005/Atom}published"]) or None
            guid = _find_text(it, ["guid", "{http://www.w3.org/2005/Atom}id"]) or None
            rec = {"title": title, "url": link or "", "summary": summary, "published": published}
            if guid:
                rec["guid"] = guid
            items.append(rec)
        return {
            "status": 200,
            "items": items,
            "etag": resp.headers.get("ETag"),
            "last_modified": resp.headers.get("Last-Modified"),
        }
    except Exception as e:
        logger.debug(f"fetch_rss_feed error: {e}")
        return {"status": 500, "items": []}
