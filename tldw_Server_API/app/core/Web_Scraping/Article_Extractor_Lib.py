# Article_Extractor_Lib.py
#########################################
# Article Extraction Library
# This library is used to handle scraping and extraction of articles from web pages.
#
####################
# Function List
#
# 1. get_page_title(url)
# 2. get_article_text(url)
# 3. get_article_title(article_url_arg)
#
####################
#
# Import necessary libraries
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import os
import random
import time
import re
import tempfile
from typing import Any, Dict, List, Union, Optional, Tuple
#
# 3rd-Party Imports
import asyncio
from urllib.parse import (
    urljoin,
    urlparse
)
from xml.dom import minidom
import xml.etree.ElementTree as xET
#
# External Libraries
from bs4 import BeautifulSoup
import aiohttp
import pandas as pd
from playwright.async_api import (
    TimeoutError,
    async_playwright
)
from playwright.sync_api import sync_playwright
import requests
import trafilatura
from tqdm import tqdm

from tldw_Server_API.app.core.DB_Management.DB_Manager import ingest_article_to_db, create_media_database
#
# Import Local
from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze
from tldw_Server_API.app.core.Metrics.metrics_logger import log_histogram, log_counter
from tldw_Server_API.app.core.Utils.Utils import logging
from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import RateLimiter
from tldw_Server_API.app.core.Web_Scraping.scraper_router import ScraperRouter
from tldw_Server_API.app.core.Web_Scraping.ua_profiles import (
    build_browser_headers,
    pick_ua_profile,
)
from tldw_Server_API.app.core.http_client import fetch as http_fetch
from urllib.robotparser import RobotFileParser
from pathlib import Path
from tldw_Server_API.app.core.Web_Scraping.filters import (
    FilterChain,
    URLPatternFilter,
    ContentTypeFilter,
)

#
#######################################################################################################################
# Function Definitions
#

# FIXME - Add a config file option/check for the user agent
web_scraping_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _default_rules_path() -> str:
    # Resolve project root: .../tldw_Server_API/app/core/Web_Scraping/Article_Extractor_Lib.py -> project root
    here = Path(__file__).resolve()
    project_root = here.parents[4]  # tldw_Server_API/ at index 3; repo root at 4
    return str(project_root / "tldw_Server_API" / "Config_Files" / "custom_scrapers.yaml")


def _merge_cookie_list_to_map(custom_cookies: Optional[List[Dict[str, Any]]]) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    if not custom_cookies:
        return cookies
    for c in custom_cookies:
        if isinstance(c, dict) and "name" in c and "value" in c:
            cookies[str(c["name"])] = str(c["value"])
    return cookies


def _robots_url_for(target_url: str) -> str:
    p = urlparse(target_url)
    return f"{p.scheme}://{p.netloc}/robots.txt"


def _js_required(html: str, headers: Dict[str, Any]) -> bool:
    """Heuristics to detect pages that require JS rendering.

    Signals fallback to Playwright when:
    - Contains noscript prompts to enable JavaScript
    - Shows common interstitials (Cloudflare/CAPTCHA)
    - HTML very small with many scripts
    - Meta refresh redirect without content
    """
    try:
        text = html.lower()
        if not text:
            return True
        # Common phrases
        js_phrases = (
            "enable javascript",
            "please enable javascript",
            "requires javascript",
            "enable your javascript",
        )
        if any(p in text for p in js_phrases):
            return True
        # Cloudflare / anti-bot hints
        if "cf-chl-bypass" in text or "cloudflare" in text and "checking your browser" in text:
            return True
        # Meta refresh
        if "http-equiv=\"refresh\"" in text or "http-equiv='refresh'" in text:
            # if no body text present
            if len(text) < 1200:
                return True
        # Script density heuristic
        script_count = text.count("<script")
        visible_len = len(BeautifulSoup(html, "html.parser").get_text(strip=True))
        if script_count >= 20 and visible_len < 1200:
            return True
    except Exception:
        return False
    return False


def _resp_get(resp: Any, key: str, default: Any = None) -> Any:
    """Best-effort fetch of a key from a response-like object.

    Supports mapping-like objects, dotted attributes, and objects exposing a
    'data' dict. Falls back to default if missing.
    """
    try:
        if isinstance(resp, dict):
            return resp.get(key, default)
        # Mapping-like via __getitem__
        try:
            return resp[key]  # type: ignore[index]
        except Exception:
            pass
        # Direct attribute
        v = getattr(resp, key, None)
        if v is not None:
            return v
        # Nested 'data' mapping commonly used in tests/doubles
        data = getattr(resp, "data", None)
        if isinstance(data, dict):
            return data.get(key, default)
    except Exception:
        return default
    return default


def is_allowed_by_robots(url: str, user_agent: str, *, backend: str = "httpx", timeout: float = 5.0) -> bool:
    """Check robots.txt for allow/deny. Fails open (allow) if robots not reachable.

    Enforces egress policy via http_client.fetch().
    """
    try:
        robots_url = _robots_url_for(url)
        resp = http_fetch(robots_url, method="GET", backend=backend, timeout=timeout, allow_redirects=True)
        if resp["status"] >= 400 or not resp["text"]:
            return True  # treat missing/unreadable robots as allow
        rp = RobotFileParser()
        rp.parse(resp["text"].splitlines())
        return bool(rp.can_fetch(user_agent, url))
    except Exception:
        # On any error, allow by default to avoid false negatives
        return True


async def is_allowed_by_robots_async(url: str, user_agent: str, *, backend: str = "httpx", timeout: float = 5.0) -> bool:
    """Async robots.txt check using asyncio.to_thread for network fetch."""
    try:
        robots_url = _robots_url_for(url)
        resp = await asyncio.to_thread(
            http_fetch,
            robots_url,
            method="GET",
            backend=backend,
            timeout=timeout,
            allow_redirects=True,
        )
        if resp["status"] >= 400 or not resp["text"]:
            return True
        rp = RobotFileParser()
        rp.parse(resp["text"].splitlines())
        return bool(rp.can_fetch(user_agent, url))
    except Exception:
        return True


DEFAULT_BOILERPLATE_PATTERNS = [
    r"\bsubscribe\s+now\b",
    r"\bsubscribe\s+today\b",
    r"\bsign\s+up\b",
    r"\bshare\s+this\b",
    r"\bshare\s+on\s+(facebook|twitter|linkedin|reddit)\b",
    r"\bfollow\s+us\b",
    r"\bnewsletter\b",
    r"\bread\s+more\b",
    r"\bthanks\s+for\s+reading\b",
]

_BOILERPLATE_REGEXES = [re.compile(pattern, re.IGNORECASE) for pattern in DEFAULT_BOILERPLATE_PATTERNS]


def _strip_boilerplate_sections(text: str) -> str:
    """Remove common boilerplate phrases from extracted article text."""
    if not text:
        return text

    lines = text.splitlines()

    def _is_boilerplate(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        return any(regex.search(stripped) for regex in _BOILERPLATE_REGEXES)

    filtered_lines: List[str] = [line for line in lines if not _is_boilerplate(line)]

    # Collapse consecutive blank lines introduced by removals.
    collapsed: List[str] = []
    previous_blank = False
    for line in filtered_lines:
        if line.strip():
            collapsed.append(line)
            previous_blank = False
        else:
            if not previous_blank:
                collapsed.append(line)
            previous_blank = True

    return "\n".join(collapsed)

#################################################################
#
# Scraping-related functions:

def get_page_title(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('title')
            title = title_tag.string.strip() if title_tag and title_tag.string else "Untitled"
            log_counter("page_title_extracted", labels={"success": "true"})
            return title
        else: #debug code for problem in suceeded request but non 200 code
            logging.error(f"Failed to fetch {url}, status code: {response.status_code}")
            return "Untitled"
    except requests.RequestException as e:
        logging.error(f"Error fetching page title: {e}")
        log_counter("page_title_extracted", labels={"success": "false"})
        return "Untitled"


def extract_article_data_from_html(html: str, url: str) -> Dict[str, Any]:
    """Extract article metadata and body from raw HTML."""
    logging.info(f"Extracting article data from HTML for {url}")
    downloaded = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        include_images=False,
    )
    downloaded = _strip_boilerplate_sections(downloaded)
    metadata = trafilatura.extract_metadata(html)

    result: Dict[str, Any] = {
        "title": "N/A",
        "author": "N/A",
        "content": "",
        "date": "N/A",
        "url": url,
        "extraction_successful": False,
    }

    if downloaded:
        logging.info(f"Content extracted successfully from {url}")
        log_counter("article_extracted", labels={"success": "true", "url": url})
        result["content"] = ContentMetadataHandler.format_content_with_metadata(
            url=url,
            content=downloaded,
            pipeline="Trafilatura",
            additional_metadata={
                "extracted_date": metadata.date if metadata and metadata.date else "N/A",
                "author": metadata.author if metadata and metadata.author else "N/A",
            },
        )
        result["extraction_successful"] = True
    else:
        log_counter("article_extracted", labels={"success": "false", "url": url})
        logging.warning("Content extraction failed.")

    if metadata:
        result.update(
            {
                "title": metadata.title if metadata.title else "N/A",
                "author": metadata.author if metadata.author else "N/A",
                "date": metadata.date if metadata.date else "N/A",
            }
        )
    else:
        logging.warning("Metadata extraction failed.")

    return result


def convert_html_to_markdown(html: str) -> str:
    """Convert raw HTML to Markdown-friendly plain text."""
    logging.info("Converting HTML to Markdown")
    soup = BeautifulSoup(html, "html.parser")
    for para in soup.find_all("p"):
        para.append("\n")
    return soup.get_text(separator="\n\n")


async def scrape_article(url: str, custom_cookies: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    logging.info(f"Scraping article from URL: {url}")
    # Enforce centralized egress/SSRF policy before any network access
    try:
        from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
        pol = evaluate_url_policy(url)
        if not getattr(pol, 'allowed', False):
            logging.error(f"Egress denied for scrape target: {getattr(pol, 'reason', 'blocked')}")
            return {
                "url": url,
                "title": "N/A",
                "author": "N/A",
                "date": "N/A",
                "content": "",
                "extraction_successful": False,
                "error": f"Egress denied: {getattr(pol, 'reason', 'blocked')}"
            }
    except Exception as _e:
        logging.error(f"Egress policy evaluation failed: {_e}")
        return {
            "url": url,
            "title": "N/A",
            "author": "N/A",
            "date": "N/A",
            "content": "",
            "extraction_successful": False,
            "error": f"Egress policy evaluation failed: {_e}"
        }
    # Resolve scraper plan via router (configurable via YAML)
    try:
        cfg = load_and_log_configs() or {}
        ws_cfg = cfg.get('web_scraper', {}) or {}
        rules_path = ws_cfg.get('custom_scrapers_yaml_path', _default_rules_path())
        rules = ScraperRouter.load_rules_from_yaml(rules_path)
        ua_mode = str(ws_cfg.get('web_scraper_ua_mode', 'fixed') or 'fixed')
        respect_robots_default = ws_cfg.get('web_scraper_respect_robots', True)
        if isinstance(respect_robots_default, str):
            respect_robots_default = respect_robots_default.strip().lower() in {"1", "true", "yes", "on"}
        router = ScraperRouter(rules, ua_mode=ua_mode, default_respect_robots=bool(respect_robots_default))
        plan = router.resolve(url)
    except Exception:
        # Safe default plan
        class _P:  # minimal stand-in
            backend = "auto"
            ua_profile = pick_ua_profile("fixed")
            impersonate = None
            extra_headers = {}
            cookies = {}
            respect_robots = True

        plan = _P()  # type: ignore

    # Build effective headers from UA profile + extras
    ua_headers = build_browser_headers(plan.ua_profile, accept_lang="en-US,en;q=0.9")
    if isinstance(plan.extra_headers, dict) and plan.extra_headers:
        ua_headers.update({str(k): str(v) for k, v in plan.extra_headers.items()})

    # robots.txt enforcement (fail open if error)
    effective_ua = ua_headers.get("User-Agent", web_scraping_user_agent)
    if getattr(plan, "respect_robots", True):
        if not await is_allowed_by_robots_async(url, effective_ua, backend="httpx"):
            logging.warning("Robots policy disallows fetching this URL; skipping fetch")
            try:
                parsed = urlparse(url)
                log_counter("scrape_blocked_by_robots_total", labels={"domain": parsed.netloc})
            except Exception:
                log_counter("scrape_blocked_by_robots_total", labels={})
            return {
                "url": url,
                "title": "N/A",
                "author": "N/A",
                "date": "N/A",
                "content": "",
                "extraction_successful": False,
                "error": "Blocked by robots policy",
            }

    # First try lightweight HTTP path (curl/httpx) before Playwright
    try:
        cookies_map = _merge_cookie_list_to_map(custom_cookies)
        # Combine with plan cookies (plan cookies win)
        if getattr(plan, "cookies", {}):
            cookies_map.update({str(k): str(v) for k, v in plan.cookies.items()})

        t0 = time.time()
        resp = await asyncio.to_thread(
            http_fetch,
            url,
            method="GET",
            headers=ua_headers,
            cookies=cookies_map or None,
            backend=(
                (str(ws_cfg.get('web_scraper_default_backend')).lower().strip() if ws_cfg.get('web_scraper_default_backend') else None)
                if getattr(plan, "backend", "auto") == "auto"
                else getattr(plan, "backend", "auto")
            ) or getattr(plan, "backend", "auto"),
            impersonate=getattr(plan, "impersonate", None),
            http2=True,
            timeout=15.0,
            allow_redirects=True,
            proxies=getattr(plan, "proxies", None) or None,
        )
        elapsed = max(0.0, time.time() - t0)
        log_histogram("scrape_fetch_latency_seconds", elapsed, labels={"backend": _resp_get(resp, "backend", "unknown")})

        if int(resp["status"]) < 400 and resp["text"]:
            # JS-required detection heuristic: decide earlier fallback
            if _js_required(resp["text"], _resp_get(resp, "headers", {})):
                log_counter("scrape_playwright_fallback_total", labels={"reason": "js_required"})
                raise RuntimeError("js_required_detected")
            article_data = extract_article_data_from_html(resp["text"], url)
            if article_data.get("extraction_successful"):
                article_data["content"] = convert_html_to_markdown(article_data["content"])
                logging.info(f"Article content length: {len(article_data['content'])}")
                log_histogram("article_content_length", len(article_data["content"]), labels={"url": url})
                log_counter("scrape_fetch_total", labels={"backend": _resp_get(resp, "backend", "unknown"), "outcome": "success"})
                return article_data
        # No extractable content
        log_counter("scrape_fetch_total", labels={"backend": _resp_get(resp, "backend", "unknown"), "outcome": "no_extract"})
    except Exception as _e:
        logging.debug(f"Lightweight fetch path failed or yielded no extractable content: {_e}")
        log_counter("scrape_fetch_total", labels={"backend": getattr(plan, "backend", "auto"), "outcome": "error"})
        log_counter("scrape_playwright_fallback_total", labels={"reason": "error"})
    else:
        # Falling back due to no extractable content
        log_counter("scrape_playwright_fallback_total", labels={"reason": "no_extract"})

    async def fetch_html(url: str) -> str:
        # Load and log the configuration
        loaded_config = load_and_log_configs()

        # load retry count from config
        scrape_retry_count = loaded_config['web_scraper'].get('web_scraper_retry_count', 3)
        retries = int(scrape_retry_count) if isinstance(scrape_retry_count, str) else scrape_retry_count
        # Load retry timeout value from config
        web_scraper_retry_timeout = loaded_config['web_scraper'].get('web_scraper_retry_timeout', 60)
        # Interpret config as seconds; Playwright expects milliseconds
        timeout_sec = int(web_scraper_retry_timeout) if isinstance(web_scraper_retry_timeout, str) else web_scraper_retry_timeout
        timeout_ms = max(0, int(timeout_sec) * 1000)

        # Whether stealth mode is enabled
        stealth_raw = loaded_config['web_scraper'].get('web_scraper_stealth_playwright', False)
        if isinstance(stealth_raw, str):
            stealth_enabled = stealth_raw.strip().lower() in {"1", "true", "yes", "on"}
        else:
            stealth_enabled = bool(stealth_raw)

        for attempt in range(retries):  # Introduced a retry loop to attempt fetching HTML multiple times
            browser = None
            try:
                logging.info(f"Fetching HTML from {url} (Attempt {attempt + 1}/{retries})")
                t0 = time.time()
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent=effective_ua,
                        # Simulating a normal browser window size for better compatibility
                        viewport={"width": 1280, "height": 720},
                    )
                    if custom_cookies:
                        # Apply cookies if provided
                        await context.add_cookies(custom_cookies)

                    page = await context.new_page()

                    # Check if stealth mode is enabled in the config
                    if stealth_enabled:
                        try:
                            from playwright_stealth import stealth_async
                            await stealth_async(page)
                        except ImportError:
                            # Fallback if stealth_async is not available
                            logging.debug("playwright_stealth not properly installed, skipping stealth mode")

                    # Navigate to the URL
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)


                   # If stealth is enabled, give the page extra time to finish loading/spawning content
                    if stealth_enabled:
                        # Try to get from config, fallback to hardcoded default
                        try:
                            from tldw_Server_API.app.core.config import config
                            stealth_wait_ms = config.get("STEALTH_WAIT_MS", 5000)
                        except Exception as e:
                            logger.debug(f"Falling back to default STEALTH_WAIT_MS; error={e}")
                            stealth_wait_ms = 5000
                        await page.wait_for_timeout(stealth_wait_ms)  # configurable delay
                    else:
                        # Alternatively, wait for network to be idle
                        await page.wait_for_load_state("networkidle", timeout=timeout_ms)

                    # Capture final HTML
                    content = await page.content()

                    # Metrics for Playwright path
                    elapsed = max(0.0, time.time() - t0)
                    log_histogram("scrape_fetch_latency_seconds", elapsed, labels={"backend": "playwright"})
                    log_counter("scrape_fetch_total", labels={"backend": "playwright", "outcome": "success"})
                    logging.info(f"HTML fetched successfully from {url}")
                    log_counter("html_fetched", labels={"url": url})

                # Return the scraped HTML
                return content

            except Exception as e:
                logging.error(f"Error fetching HTML from {url} on attempt {attempt + 1}: {e}")
                log_counter("scrape_fetch_total", labels={"backend": "playwright", "outcome": "error"})

                if attempt < retries - 1:
                    logging.info("Retrying...")
                    await asyncio.sleep(2)
                else:
                    logging.error("Max retries reached, giving up on this URL.")
                    log_counter("html_fetch_error", labels={"url": url, "error": str(e)})
                    return ""  # Return empty string on final failure

            finally:
                # Ensure the browser is closed before returning
                if browser is not None:
                    await browser.close()

        # If for some reason you exit the loop without returning (unlikely), return empty string
        return ""

    html = await fetch_html(url)
    article_data = extract_article_data_from_html(html, url)
    if article_data['extraction_successful']:
        article_data['content'] = convert_html_to_markdown(article_data['content'])
        logging.info(f"Article content length: {len(article_data['content'])}")
        log_histogram("article_content_length", len(article_data['content']), labels={"url": url})
    return article_data


def scrape_article_blocking(url: str, custom_cookies: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Blocking scraper for synchronous code paths.

    Fetches HTML with requests using a desktop-like user agent and optional cookies,
    then extracts article content via trafilatura and converts to display text.
    """
    try:
        # Egress guard
        try:
            from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
            pol = evaluate_url_policy(url)
            if not getattr(pol, 'allowed', False):
                return {"url": url, "title": "N/A", "author": "N/A", "date": "N/A", "content": "", "extraction_successful": False, "error": f"Egress denied: {getattr(pol, 'reason', 'blocked')}"}
        except Exception as _e:
            return {"url": url, "title": "N/A", "author": "N/A", "date": "N/A", "content": "", "extraction_successful": False, "error": f"Egress policy evaluation failed: {_e}"}

        headers = {"User-Agent": web_scraping_user_agent}
        session = requests.Session()
        session.headers.update(headers)
        # If cookies are provided in Playwright-style dicts, reduce to name->value
        if custom_cookies:
            for c in custom_cookies:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    session.cookies.set(c["name"], c["value"])
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            logging.error(f"Failed to fetch {url}, status: {resp.status_code}")
            return {"url": url, "title": "N/A", "author": "N/A", "date": "N/A", "content": "", "extraction_successful": False}

        article_data = extract_article_data_from_html(resp.text, url)
        if article_data.get("extraction_successful"):
            article_data["content"] = convert_html_to_markdown(article_data["content"])
        return article_data
    except Exception as e:
        logging.error(f"Blocking scrape failed for {url}: {e}")
        return {"url": url, "title": "N/A", "author": "N/A", "date": "N/A", "content": "", "extraction_successful": False}


# FIXME - Add keyword integration/tagging
async def scrape_and_summarize_multiple(
    urls: str,
    custom_prompt_arg: Optional[str],
    api_name: str,
    api_key: Optional[str],
    keywords: str,
    custom_article_titles: Optional[str],
    system_message: Optional[str] = None,
    summarize_checkbox: bool = False,
    custom_cookies: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.7
) -> List[Dict[str, Any]]:
    urls_list = [url.strip() for url in urls.split('\n') if url.strip()]
    custom_titles = custom_article_titles.split('\n') if custom_article_titles else []

    results = []
    errors = []

    # Create a tqdm progress bar
    progress_bar = tqdm(total=len(urls_list), desc="Scraping and Summarizing")

    # Loop over each URL to scrape and optionally summarize
    for i, url in enumerate(urls_list):
        custom_title = custom_titles[i] if i < len(custom_titles) else None
        try:
            # Scrape the article
            article = await scrape_article(url, custom_cookies=custom_cookies)
            if article and article['extraction_successful']:
                log_counter("article_scraped", labels={"success": "true", "url": url})
                if custom_title:
                    article['title'] = custom_title

                # If summarization is requested
                if summarize_checkbox:
                    content = article.get('content', '')
                    if content:
                        # Prepare prompts
                        system_message_final = system_message or \
                                               "Act as a professional summarizer and summarize this article."
                        article_custom_prompt = custom_prompt_arg or \
                                                "Act as a professional summarizer and summarize this article."

                        # Summarize the content using the summarize function
                        summary = analyze(
                            input_data=content,
                            custom_prompt_arg=article_custom_prompt,
                            api_name=api_name,
                            api_key=api_key,
                            temp=temperature,
                            system_message=system_message_final
                        )
                        article['summary'] = summary
                        log_counter("article_summarized", labels={"success": "true", "url": url})
                        logging.info(f"Summary generated for URL {url}")
                    else:
                        article['summary'] = "No content available to summarize."
                        logging.warning(f"No content to summarize for URL {url}")
                else:
                    article['summary'] = None

                results.append(article)
            else:
                error_message = f"Extraction unsuccessful for URL {url}"
                errors.append(error_message)
                logging.error(error_message)
                log_counter("article_scraped", labels={"success": "false", "url": url})
        except Exception as e:
            log_counter("article_processing_error", labels={"url": url})
            error_message = f"Error processing URL {i + 1} ({url}): {str(e)}"
            errors.append(error_message)
            logging.error(error_message, exc_info=True)
        finally:
            # Update the progress bar
            progress_bar.update(1)

    # Close the progress bar
    progress_bar.close()

    if errors:
        logging.error("\n".join(errors))

    if not results:
        logging.error("No articles were successfully scraped and summarized/analyzed.")
        return []

    log_histogram("articles_processed", len(results))
    return results


async def async_scrape_and_no_summarize_then_ingest(url, keywords, custom_article_title):
    try:
        # Step 1: Scrape the article
        article_data = await scrape_article(url)
        if not article_data:
            log_counter("article_scrape_failed", labels={"url": url})
            return "Failed to scrape the article."

        # Use the custom title if provided, otherwise use the scraped title
        title = custom_article_title.strip() if custom_article_title else article_data.get('title', 'Untitled')
        author = article_data.get('author', 'Unknown')
        content = article_data.get('content', '')
        ingestion_date = datetime.now().strftime('%Y-%m-%d')

        # Step 2: Ingest the article into the database
        db_instance = create_media_database(client_id="article_extractor")
        # Ensure keywords list
        kw_list = [kw.strip() for kw in str(keywords).split(',')] if isinstance(keywords, str) else (keywords or [])
        ingestion_result = ingest_article_to_db(
            db_instance=db_instance,
            url=url,
            title=title,
            author=author,
            content=content,
            keywords=kw_list,
            ingestion_date=ingestion_date,
            custom_prompt=None,
            summary=None,
        )
        log_counter("article_ingested", labels={"success": str(ingestion_result).lower(), "url": url})

        # When displaying content, we might want to strip metadata
        display_content = ContentMetadataHandler.strip_metadata(content)
        return f"Title: {title}\nAuthor: {author}\nIngestion Result: {ingestion_result}\n\nArticle Contents: {display_content}"
    except Exception as e:
        log_counter("article_processing_error", labels={"url": url})
        logging.error(f"Error processing URL {url}: {str(e)}")
        return f"Failed to process URL {url}: {str(e)}"

def scrape_and_no_summarize_then_ingest(url, keywords, custom_article_title):
    """Synchronous wrapper for CLI usage.

    In async contexts, prefer calling async_scrape_and_no_summarize_then_ingest.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_scrape_and_no_summarize_then_ingest(url, keywords, custom_article_title))
    raise RuntimeError("Call async_scrape_and_no_summarize_then_ingest() within async contexts")


def scrape_from_filtered_sitemap(sitemap_file: str, filter_function) -> list:
    """
    Scrape articles from a sitemap file, applying an additional filter function.

    :param sitemap_file: Path to the sitemap file
    :param filter_function: A function that takes a URL and returns True if it should be scraped
    :return: List of scraped articles
    """
    try:
        tree = xET.parse(sitemap_file)
        root = tree.getroot()

        articles = []
        for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
            if filter_function(url.text):
                article_data = scrape_article_blocking(url.text)
                if article_data:
                    articles.append(article_data)

        return articles
    except xET.ParseError as e:
        logging.error(f"Error parsing sitemap: {e}")
        return []


def is_content_page(url: str) -> bool:
    """
    Determine if a URL is likely to be a content page.
    This is a basic implementation and may need to be adjusted based on the specific website structure.

    :param url: The URL to check
    :return: True if the URL is likely a content page, False otherwise
    """
    # Exclude common non-content pages
    exclude_patterns = [
        '/tag/', '/category/', '/author/', '/search/', '/page/',
        'wp-content', 'wp-includes', 'wp-json', 'wp-admin',
        'login', 'register', 'cart', 'checkout', 'account',
        '.jpg', '.png', '.gif', '.pdf', '.zip'
    ]
    chain = FilterChain([
        ContentTypeFilter(),
        URLPatternFilter(include_patterns=None, exclude_patterns=exclude_patterns)
    ])
    return chain.apply(url)

def scrape_and_convert_with_filter(source: str, output_file: str, filter_function=is_content_page, level: int = None):
    """
    Scrape articles from a sitemap or by URL level, apply filtering, and convert to a single markdown file.

    :param source: URL of the sitemap, base URL for level-based scraping, or path to a local sitemap file
    :param output_file: Path to save the output markdown file
    :param filter_function: Function to filter URLs (default is is_content_page)
    :param level: URL level for scraping (None if using sitemap)
    """
    if level is not None:
        # Scraping by URL level
        articles = scrape_by_url_level(source, level)
        articles = [article for article in articles if filter_function(article['url'])]
    elif source.startswith('http'):
        # Scraping from online sitemap
        articles = scrape_from_sitemap(source)
        articles = [article for article in articles if filter_function(article['url'])]
    else:
        # Scraping from local sitemap file
        articles = scrape_from_filtered_sitemap(source, filter_function)

    articles = [article for article in articles if filter_function(article['url'])]
    markdown_content = convert_to_markdown(articles)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    logging.info(f"Scraped and filtered content saved to {output_file}")


async def scrape_entire_site(base_url: str) -> List[Dict]:
    """
    Scrape the entire site by generating a temporary sitemap and extracting content from each page.

    :param base_url: The base URL of the site to scrape
    :return: A list of dictionaries containing scraped article data
    """
    # Step 1: Collect internal links from the site (async, with rate limiting)
    try:
        rate = RateLimiter(max_requests_per_second=1.5, max_requests_per_minute=60, max_requests_per_hour=1000)
    except Exception:
        rate = None
    links = await async_collect_internal_links(base_url, rate_limiter=rate)
    log_histogram("internal_links_collected", len(links), labels={"base_url": base_url})
    logging.info(f"Collected {len(links)} internal links.")

    # Step 2: Generate the temporary sitemap
    temp_sitemap_path = generate_temp_sitemap_from_links(links)

    # Step 3: Scrape each URL in the sitemap
    scraped_articles = []
    try:
        async def scrape_and_log(link):
            logging.info(f"Scraping {link} ...")
            article_data = await scrape_article(link)

            if article_data:
                logging.info(f"Title: {article_data['title']}")
                logging.info(f"Author: {article_data['author']}")
                logging.info(f"Date: {article_data['date']}")
                logging.info(f"Content: {article_data['content'][:500]}...")

                return article_data
            return None

        # Use asyncio.gather to scrape multiple articles concurrently
        scraped_articles = await asyncio.gather(*[scrape_and_log(link) for link in links])
        # Remove any None values (failed scrapes)
        scraped_articles = [article for article in scraped_articles if article is not None]
        log_histogram("articles_scraped", len(scraped_articles), labels={"base_url": base_url})

    finally:
        # Clean up the temporary sitemap file
        os.unlink(temp_sitemap_path)
        logging.info("Temporary sitemap file deleted")

    return scraped_articles


def scrape_by_url_level(base_url: str, level: int) -> list:
    """Scrape articles from URLs up to a certain level under the base URL."""

    def get_url_level(url: str) -> int:
        return len(urlparse(url).path.strip('/').split('/'))

    links = collect_internal_links(base_url)
    filtered_links = [link for link in links if get_url_level(link) <= level]

    results = []
    for link in filtered_links:
        article = scrape_article_blocking(link)
        if article:
            results.append(article)
    return results


def scrape_from_sitemap(sitemap_url: str) -> list:
    """Scrape articles from a sitemap URL."""
    try:
        # Egress guard
        try:
            from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
            pol = evaluate_url_policy(sitemap_url)
            if not getattr(pol, 'allowed', False):
                logging.error(f"Egress denied for sitemap: {getattr(pol, 'reason', 'blocked')}")
                return []
        except Exception as _e:
            logging.error(f"Egress policy evaluation failed: {_e}")
            return []

        # Avoid passing kwargs to allow simple monkeypatch fakes in tests
        response = requests.get(sitemap_url)
        response.raise_for_status()
        root = xET.fromstring(response.content)

        results = []
        for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
            article = scrape_article_blocking(url.text)
            if article:
                results.append(article)
        return results
    except requests.RequestException as e:
        logging.error(f"Error fetching sitemap: {e}")
        return []

#
# End of Scraping Functions
#######################################################
#
# Sitemap/Crawling-related Functions


def collect_internal_links(base_url: str) -> set:
    visited = set()
    to_visit = {base_url}

    # Egress guard
    try:
        from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
        pol = evaluate_url_policy(base_url)
        if not getattr(pol, 'allowed', False):
            logging.error(f"Egress denied for base URL: {getattr(pol, 'reason', 'blocked')}")
            return visited
    except Exception as _e:
        logging.error(f"Egress policy evaluation failed: {_e}")
        return visited

    while to_visit:
        current_url = to_visit.pop()
        if current_url in visited:
            continue

        try:
            response = requests.get(current_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Collect internal links
            for link in soup.find_all('a', href=True):
                full_url = urljoin(base_url, link['href'])
                # Only process links within the same domain
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    if full_url not in visited:
                        to_visit.add(full_url)

            visited.add(current_url)
        except requests.RequestException as e:
            logging.error(f"Error visiting {current_url}: {e}")
            continue

    return visited


async def async_collect_internal_links(base_url: str,
                                       max_pages: int = 500,
                                       rate_limiter: Optional[RateLimiter] = None,
                                       request_timeout: int = 20) -> set:
    """Async internal link collector using aiohttp and optional rate limiter."""
    visited: set = set()
    to_visit: set = {base_url}

    headers = {"User-Agent": web_scraping_user_agent}
    timeout = aiohttp.ClientTimeout(total=request_timeout)

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        while to_visit and len(visited) < max_pages:
            current_url = to_visit.pop()
            if current_url in visited:
                continue
            try:
                if rate_limiter:
                    await rate_limiter.acquire()
                async with session.get(current_url) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
            except Exception:
                continue

            visited.add(current_url)
            try:
                soup = BeautifulSoup(text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    full_url = urljoin(base_url, link['href'])
                    if urlparse(full_url).netloc == urlparse(base_url).netloc:
                        if full_url not in visited:
                            to_visit.add(full_url)
            except Exception:
                continue

    return visited

def generate_temp_sitemap_from_links(links: set) -> str:
    """
    Generate a temporary sitemap file from collected links and return its path.

    :param links: A set of URLs to include in the sitemap
    :return: Path to the temporary sitemap file
    """
    # Create the root element
    urlset = xET.Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    # Add each link to the sitemap
    for link in links:
        url = xET.SubElement(urlset, "url")
        loc = xET.SubElement(url, "loc")
        loc.text = link
        lastmod = xET.SubElement(url, "lastmod")
        lastmod.text = datetime.now().strftime("%Y-%m-%d")
        changefreq = xET.SubElement(url, "changefreq")
        changefreq.text = "daily"
        priority = xET.SubElement(url, "priority")
        priority.text = "0.5"

    # Create the tree and get it as a string
    xml_string = xET.tostring(urlset, 'utf-8')

    # Pretty print the XML
    pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="  ")

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as temp_file:
        temp_file.write(pretty_xml)
        temp_file_path = temp_file.name

    logging.info(f"Temporary sitemap created at: {temp_file_path}")
    return temp_file_path


def generate_sitemap_for_url(url: str) -> List[Dict[str, str]]:
    """
    Generate a sitemap for the given URL using the create_filtered_sitemap function.

    Args:
        url (str): The base URL to generate the sitemap for

    Returns:
        List[Dict[str, str]]: A list of dictionaries, each containing 'url' and 'title' keys
    """
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".xml", delete=False) as temp_file:
        create_filtered_sitemap(url, temp_file.name, is_content_page)
        temp_file.seek(0)
        tree = xET.parse(temp_file.name)
        root = tree.getroot()

        sitemap = []
        for url_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
            loc = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text
            sitemap.append({"url": loc, "title": loc.split("/")[-1] or url})  # Use the last part of the URL as a title

    return sitemap

def create_filtered_sitemap(base_url: str, output_file: str, filter_function):
    """
    Create a sitemap from internal links and filter them based on a custom function.

    :param base_url: The base URL of the website
    :param output_file: The file to save the sitemap to
    :param filter_function: A function that takes a URL and returns True if it should be included
    """
    links = collect_internal_links(base_url)
    filtered_links = set(filter(filter_function, links))

    root = xET.Element("urlset")
    root.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    for link in filtered_links:
        url = xET.SubElement(root, "url")
        loc = xET.SubElement(url, "loc")
        loc.text = link

    tree = xET.ElementTree(root)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"Filtered sitemap saved to {output_file}")


#
# End of Crawling Functions
#################################################################
#
# Utility Functions

def convert_to_markdown(articles: list) -> str:
    """Convert a list of article data into a single markdown document."""
    markdown = ""
    for article in articles:
        markdown += f"# {article['title']}\n\n"
        markdown += f"Author: {article['author']}\n"
        markdown += f"Date: {article['date']}\n\n"
        markdown += f"{article['content']}\n\n"
        markdown += "---\n\n"  # Separator between articles
    return markdown

def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def load_hashes(filename: str) -> Dict[str, str]:
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    else:
        return {}

def save_hashes(hashes: Dict[str, str], filename: str):
    with open(filename, 'w') as f:
        json.dump(hashes, f)

def has_page_changed(url: str, new_hash: str, stored_hashes: Dict[str, str]) -> bool:
    old_hash = stored_hashes.get(url)
    return old_hash != new_hash


#
#
###################################################
#
# Bookmark Parsing Functions

def parse_chromium_bookmarks(json_data: dict) -> Dict[str, Union[str, List[str]]]:
    """
    Parse Chromium-based browser bookmarks from JSON data.

    :param json_data: The JSON data from the bookmarks file
    :return: A dictionary with bookmark names as keys and URLs as values or lists of URLs if duplicates exist
    """
    bookmarks = {}

    def recurse_bookmarks(nodes):
        for node in nodes:
            if node.get('type') == 'url':
                name = node.get('name')
                url = node.get('url')
                if name and url:
                    if name in bookmarks:
                        if isinstance(bookmarks[name], list):
                            bookmarks[name].append(url)
                        else:
                            bookmarks[name] = [bookmarks[name], url]
                    else:
                        bookmarks[name] = url
            elif node.get('type') == 'folder' and 'children' in node:
                recurse_bookmarks(node['children'])

    # Chromium bookmarks have a 'roots' key
    if 'roots' in json_data:
        for root in json_data['roots'].values():
            if 'children' in root:
                recurse_bookmarks(root['children'])
    else:
        recurse_bookmarks(json_data.get('children', []))

    return bookmarks


def parse_firefox_bookmarks(html_content: str) -> Dict[str, Union[str, List[str]]]:
    """
    Parse Firefox bookmarks from HTML content.

    :param html_content: The HTML content from the bookmarks file
    :return: A dictionary with bookmark names as keys and URLs as values or lists of URLs if duplicates exist
    """
    bookmarks = {}
    soup = BeautifulSoup(html_content, 'html.parser')

    # Firefox stores bookmarks within <a> tags inside <dt>
    for a in soup.find_all('a'):
        name = a.get_text()
        url = a.get('href')
        if name and url:
            if name in bookmarks:
                if isinstance(bookmarks[name], list):
                    bookmarks[name].append(url)
                else:
                    bookmarks[name] = [bookmarks[name], url]
            else:
                bookmarks[name] = url

    return bookmarks


def load_bookmarks(file_path: str) -> Dict[str, Union[str, List[str]]]:
    """
    Load bookmarks from a file (JSON for Chrome/Edge or HTML for Firefox).

    :param file_path: Path to the bookmarks file
    :return: A dictionary with bookmark names as keys and URLs as values or lists of URLs if duplicates exist
    :raises ValueError: If the file format is unsupported or parsing fails
    """
    if not os.path.isfile(file_path):
        logging.error(f"File '{file_path}' does not exist.")
        raise FileNotFoundError(f"File '{file_path}' does not exist.")

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == '.json' or ext == '':
        # Attempt to parse as JSON (Chrome/Edge)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            return parse_chromium_bookmarks(json_data)
        except json.JSONDecodeError:
            logging.error("Failed to parse JSON. Ensure the file is a valid Chromium bookmarks JSON file.")
            raise ValueError("Invalid JSON format for Chromium bookmarks.")
    elif ext in ['.html', '.htm']:
        # Parse as HTML (Firefox)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return parse_firefox_bookmarks(html_content)
        except Exception as e:
            logging.error(f"Failed to parse HTML bookmarks: {e}")
            raise ValueError(f"Failed to parse HTML bookmarks: {e}")
    else:
        logging.error("Unsupported file format. Please provide a JSON (Chrome/Edge) or HTML (Firefox) bookmarks file.")
        raise ValueError("Unsupported file format for bookmarks.")


def collect_bookmarks(file_path: str) -> Dict[str, Union[str, List[str]]]:
    """
    Collect bookmarks from the provided bookmarks file and return a dictionary.

    :param file_path: Path to the bookmarks file
    :return: Dictionary with bookmark names as keys and URLs as values or lists of URLs if duplicates exist
    """
    try:
        bookmarks = load_bookmarks(file_path)
        logging.info(f"Successfully loaded {len(bookmarks)} bookmarks from '{file_path}'.")
        return bookmarks
    except (FileNotFoundError, ValueError) as e:
        logging.error(f"Error loading bookmarks: {e}")
        return {}


def parse_csv_urls(file_path: str) -> Dict[str, Union[str, List[str]]]:
    """
    Parse URLs from a CSV file. The CSV should have at minimum a 'url' column,
    and optionally a 'title' or 'name' column.

    :param file_path: Path to the CSV file
    :return: Dictionary with titles/names as keys and URLs as values
    """
    try:
        # Read CSV file
        df = pd.read_csv(file_path)

        # Check if required columns exist
        if 'url' not in df.columns:
            raise ValueError("CSV must contain a 'url' column")

        # Initialize result dictionary
        urls_dict = {}

        # Determine which column to use as key
        key_column = next((col for col in ['title', 'name'] if col in df.columns), None)

        for idx in range(len(df)):
            url = df.iloc[idx]['url'].strip()

            # Use title/name if available, otherwise use URL as key
            if key_column:
                key = df.iloc[idx][key_column].strip()
            else:
                key = f"Article {idx + 1}"

            # Handle duplicate keys
            if key in urls_dict:
                if isinstance(urls_dict[key], list):
                    urls_dict[key].append(url)
                else:
                    urls_dict[key] = [urls_dict[key], url]
            else:
                urls_dict[key] = url

        return urls_dict

    except pd.errors.EmptyDataError:
        logging.error("The CSV file is empty")
        return {}
    except Exception as e:
        logging.error(f"Error parsing CSV file: {str(e)}")
        return {}


def collect_urls_from_file(file_path: str) -> Dict[str, Union[str, List[str]]]:
    """
    Unified function to collect URLs from either bookmarks or CSV files.

    :param file_path: Path to the file (bookmarks or CSV)
    :return: Dictionary with names as keys and URLs as values
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == '.csv':
        return parse_csv_urls(file_path)
    else:
        return collect_bookmarks(file_path)

# Usage:
# from Article_Extractor_Lib import collect_bookmarks
#
# # Path to your bookmarks file
# # For Chrome or Edge (JSON format)
# chromium_bookmarks_path = "/path/to/Bookmarks"
#
# # For Firefox (HTML format)
# firefox_bookmarks_path = "/path/to/bookmarks.html"
#
# # Collect bookmarks from Chromium-based browser
# chromium_bookmarks = collect_bookmarks(chromium_bookmarks_path)
# print("Chromium Bookmarks:")
# for name, url in chromium_bookmarks.items():
#     print(f"{name}: {url}")
#
# # Collect bookmarks from Firefox
# firefox_bookmarks = collect_bookmarks(firefox_bookmarks_path)
# print("\nFirefox Bookmarks:")
# for name, url in firefox_bookmarks.items():
#     print(f"{name}: {url}")

#
# End of Bookmarking Parsing Functions
#####################################################################


#####################################################################
#
# Article Scraping Metadata Functions

class ContentMetadataHandler:
    """Handles the addition and parsing of metadata for scraped content."""

    METADATA_START = "[METADATA]"
    METADATA_END = "[/METADATA]"

    @staticmethod
    def format_content_with_metadata(
            url: str,
            content: str,
            pipeline: str = "Trafilatura",
            additional_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format content with metadata header.

        Args:
            url: The source URL
            content: The scraped content
            pipeline: The scraping pipeline used
            additional_metadata: Optional dictionary of additional metadata to include

        Returns:
            Formatted content with metadata header
        """
        metadata = {
            "url": url,
            "ingestion_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content_hash": hashlib.sha256(content.encode('utf-8')).hexdigest(),
            "scraping_pipeline": pipeline
        }

        # Add any additional metadata
        if additional_metadata:
            metadata.update(additional_metadata)

        formatted_content = f"""{ContentMetadataHandler.METADATA_START}
        {json.dumps(metadata, indent=2)}
        {ContentMetadataHandler.METADATA_END}

        {content}"""

        return formatted_content

    @staticmethod
    def extract_metadata(content: str) -> Tuple[Dict[str, Any], str]:
        """
        Extract metadata and content separately.

        Args:
            content: The full content including metadata

        Returns:
            Tuple of (metadata dict, clean content)
        """
        try:
            metadata_start = content.index(ContentMetadataHandler.METADATA_START) + len(
                ContentMetadataHandler.METADATA_START)
            metadata_end = content.index(ContentMetadataHandler.METADATA_END)
            metadata_json = content[metadata_start:metadata_end].strip()
            metadata = json.loads(metadata_json)
            clean_content = content[metadata_end + len(ContentMetadataHandler.METADATA_END):].strip()
            return metadata, clean_content
        except (ValueError, json.JSONDecodeError) as e:
            return {}, content

    @staticmethod
    def has_metadata(content: str) -> bool:
        """
        Check if content contains metadata.

        Args:
            content: The content to check

        Returns:
            bool: True if metadata is present
        """
        return (ContentMetadataHandler.METADATA_START in content and
                ContentMetadataHandler.METADATA_END in content)

    @staticmethod
    def strip_metadata(content: str) -> str:
        """
        Remove metadata from content if present.

        Args:
            content: The content to strip metadata from

        Returns:
            Content without metadata
        """
        try:
            metadata_end = content.index(ContentMetadataHandler.METADATA_END)
            return content[metadata_end + len(ContentMetadataHandler.METADATA_END):].strip()
        except ValueError:
            return content

    @staticmethod
    def get_content_hash(content: str) -> str:
        """
        Get hash of content without metadata.

        Args:
            content: The content to hash

        Returns:
            SHA-256 hash of the clean content
        """
        clean_content = ContentMetadataHandler.strip_metadata(content)
        return hashlib.sha256(clean_content.encode('utf-8')).hexdigest()

    @staticmethod
    def content_changed(old_content: str, new_content: str) -> bool:
        """
        Check if content has changed by comparing hashes.

        Args:
            old_content: Previous version of content
            new_content: New version of content

        Returns:
            bool: True if content has changed
        """
        old_hash = ContentMetadataHandler.get_content_hash(old_content)
        new_hash = ContentMetadataHandler.get_content_hash(new_content)
        return old_hash != new_hash


##############################################################
#
# Scraping Functions

def get_url_depth(url: str) -> int:
    return len(urlparse(url).path.strip('/').split('/'))

def sync_recursive_scrape(url_input, max_pages, max_depth, delay=1.0, custom_cookies=None):
    def run_async_scrape():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            recursive_scrape(url_input, max_pages, max_depth, delay=delay, custom_cookies=custom_cookies)
        )

    with ThreadPoolExecutor() as executor:
        future = executor.submit(run_async_scrape)
        return future.result()

async def recursive_scrape(
        base_url: str,
        max_pages: int,
        max_depth: int,
        delay: float = 1.0,
        resume_file: str = 'scrape_progress.json',
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        custom_cookies: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[callable] = None
) -> List[Dict]:
    async def save_progress():
        temp_file = resume_file + ".tmp"
        with open(temp_file, 'w') as f:
            json.dump({
                'visited': list(visited),
                'to_visit': to_visit,
                'scraped_articles': scraped_articles,
                'pages_scraped': pages_scraped
            }, f)
        os.replace(temp_file, resume_file)  # Atomic replace

    def is_valid_url(url: str) -> bool:
        return url.startswith("http") and len(url) > 0

    # Load progress if resume file exists
    if os.path.exists(resume_file):
        with open(resume_file, 'r') as f:
            progress_data = json.load(f)
            visited = set(progress_data['visited'])
            to_visit = progress_data['to_visit']
            scraped_articles = progress_data['scraped_articles']
            pages_scraped = progress_data['pages_scraped']
    else:
        visited = set()
        to_visit = [(base_url, 0)]  # (url, depth)
        scraped_articles = []
        pages_scraped = 0

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=user_agent)

            # Set custom cookies if provided
            if custom_cookies:
                await context.add_cookies(custom_cookies)

            try:
                while to_visit and pages_scraped < max_pages:
                    current_url, current_depth = to_visit.pop(0)

                    if current_url in visited or current_depth > max_depth:
                        continue

                    visited.add(current_url)

                    # Update progress if callback provided
                    if progress_callback:
                        progress_callback(f"Scraping page {pages_scraped + 1}/{max_pages}: {current_url}")

                    try:
                        await asyncio.sleep(random.uniform(delay * 0.8, delay * 1.2))

                        article_data = await scrape_article_async(context, current_url)

                        if article_data and article_data['extraction_successful']:
                            scraped_articles.append(article_data)
                            pages_scraped += 1

                        # If we haven't reached max depth, add child links to to_visit
                        if current_depth < max_depth:
                            page = await context.new_page()
                            await page.goto(current_url)
                            await page.wait_for_load_state("networkidle")

                            links = await page.eval_on_selector_all('a[href]',
                                                                    "(elements) => elements.map(el => el.href)")
                            for link in links:
                                child_url = urljoin(base_url, link)
                                if is_valid_url(child_url) and child_url.startswith(
                                        base_url) and child_url not in visited and should_scrape_url(child_url):
                                    to_visit.append((child_url, current_depth + 1))

                            await page.close()

                    except Exception as e:
                        logging.error(f"Error scraping {current_url}: {str(e)}")

                    # Save progress periodically (e.g., every 10 pages)
                    if pages_scraped % 10 == 0:
                        await save_progress()

            finally:
                await browser.close()

    finally:
        # These statements are now guaranteed to be reached after the scraping is done
        await save_progress()

        # Remove the progress file when scraping is completed successfully
        if os.path.exists(resume_file):
            os.remove(resume_file)

        # Final progress update
        if progress_callback:
            progress_callback(f"Scraping completed. Total pages scraped: {pages_scraped}")

        return scraped_articles

async def scrape_article_async(context, url: str) -> Dict[str, Any]:
    page = await context.new_page()
    try:
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        title = await page.title()
        content = await page.content()

        return {
            'url': url,
            'title': title,
            'content': content,
            'extraction_successful': True
        }
    except Exception as e:
        logging.error(f"Error scraping article {url}: {str(e)}")
        return {
            'url': url,
            'extraction_successful': False,
            'error': str(e)
        }
    finally:
        await page.close()

def scrape_article_sync(url: str) -> Dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")

            title = page.title()
            content = page.content()

            return {
                'url': url,
                'title': title,
                'content': content,
                'extraction_successful': True
            }
        except Exception as e:
            logging.error(f"Error scraping article {url}: {str(e)}")
            return {
                'url': url,
                'extraction_successful': False,
                'error': str(e)
            }
        finally:
            browser.close()

def should_scrape_url(url: str) -> bool:
    """Deprecated: use FilterChain externally where possible.

    Kept for backward compatibility and implemented via FilterChain
    using include/exclude substring patterns and content type check.
    """
    exclude_patterns = [
        '/tag/', '/category/', '/author/', '/search/', '/page/',
        'wp-content', 'wp-includes', 'wp-json', 'wp-admin',
        'login', 'register', 'cart', 'checkout', 'account',
        '.jpg', '.png', '.gif', '.pdf', '.zip'
    ]
    include_patterns = ['/article/', '/post/', '/blog/']
    chain = FilterChain([
        ContentTypeFilter(),
        URLPatternFilter(include_patterns=include_patterns, exclude_patterns=exclude_patterns)
    ])
    return chain.apply(url)

async def scrape_with_retry(url: str, max_retries: int = 3, retry_delay: float = 5.0):
    for attempt in range(max_retries):
        try:
            return await scrape_article(url)
        except TimeoutError:
            if attempt < max_retries - 1:
                logging.warning(f"Timeout error scraping {url}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logging.error(f"Failed to scrape {url} after {max_retries} attempts.")
                return None
        except Exception as e:
            logging.error(f"Error scraping {url}: {str(e)}")
            return None

def convert_json_to_markdown(json_str: str) -> str:
    """
    Converts the JSON output from the scraping process into a markdown format.

    Args:
        json_str (str): JSON-formatted string containing the website collection data

    Returns:
        str: Markdown-formatted string of the website collection data
    """
    try:
        # Parse the JSON string
        data = json.loads(json_str)

        # Check if there's an error in the JSON
        if "error" in data:
            return f"# Error\n\n{data['error']}"

        # Start building the markdown string
        markdown = f"# Website Collection: {data['base_url']}\n\n"

        # Add metadata
        markdown += "## Metadata\n\n"
        markdown += f"- **Scrape Method:** {data['scrape_method']}\n"
        markdown += f"- **API Used:** {data['api_used']}\n"
        markdown += f"- **Keywords:** {data['keywords']}\n"
        if data.get('url_level') is not None:
            markdown += f"- **URL Level:** {data['url_level']}\n"
        if data.get('max_pages') is not None:
            markdown += f"- **Maximum Pages:** {data['max_pages']}\n"
        if data.get('max_depth') is not None:
            markdown += f"- **Maximum Depth:** {data['max_depth']}\n"
        markdown += f"- **Total Articles Scraped:** {data['total_articles_scraped']}\n\n"

        # Add URLs Scraped
        markdown += "## URLs Scraped\n\n"
        for url in data['urls_scraped']:
            markdown += f"- {url}\n"
        markdown += "\n"

        # Add the content
        markdown += "## Content\n\n"
        markdown += data['content']

        return markdown

    except json.JSONDecodeError:
        return "# Error\n\nInvalid JSON string provided."
    except KeyError as e:
        return f"# Error\n\nMissing key in JSON data: {str(e)}"
    except Exception as e:
        return f"# Error\n\nAn unexpected error occurred: {str(e)}"

#
# End of Scraping functions
##################################################################

#
# End of Article_Extractor_Lib.py
#######################################################################################################################
