from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set, Dict, Tuple
from urllib.parse import urlparse
import asyncio
import time
from urllib.robotparser import RobotFileParser
from loguru import logger

try:
    # Local HTTP client used across the project; enforces egress policy internally
    from tldw_Server_API.app.core.http_client import fetch as http_fetch
except Exception:  # pragma: no cover - defensive import to avoid runtime breakage
    http_fetch = None  # type: ignore[assignment]

try:
    # Centralized egress policy evaluator
    from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
except Exception:  # pragma: no cover - defensive import
    evaluate_url_policy = None  # type: ignore[assignment]


class URLFilter:
    """Synchronous URL filter base class."""

    def apply(self, url: str) -> bool:  # pragma: no cover - simple interface
        raise NotImplementedError


class FilterChain:
    """Apply a sequence of filters (AND semantics)."""

    def __init__(self, filters: Optional[List[URLFilter]] = None) -> None:
        self.filters = list(filters or [])

    def add(self, f: URLFilter) -> "FilterChain":
        self.filters.append(f)
        return self

    def apply(self, url: str) -> bool:
        for f in self.filters:
            if not f.apply(url):
                return False
        return True


@dataclass
class DomainFilter(URLFilter):
    """Allow/deny domains (optionally including subdomains)."""

    allowed: Optional[Set[str]] = None
    blocked: Optional[Set[str]] = None
    include_subdomains: bool = True

    def _host(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def _is_sub(self, host: str, root: str) -> bool:
        if not host or not root:
            return False
        return host == root or host.endswith("." + root)

    def apply(self, url: str) -> bool:
        host = self._host(url)
        if not host:
            return False
        # Blocked wins
        if self.blocked:
            for d in self.blocked:
                if (self._is_sub(host, d) if self.include_subdomains else host == d):
                    return False
        # If no allowed set, pass
        if not self.allowed:
            return True
        for d in self.allowed:
            if (self._is_sub(host, d) if self.include_subdomains else host == d):
                return True
        return False


class ContentTypeFilter(URLFilter):
    """Fast extension-based content filter.

    Allows typical HTML-like pages, rejects common binary/media/document types.
    """

    # Extensions to reject outright
    _REJECT_EXT = {
        # images
        "jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "tiff", "ico",
        # audio/video
        "mp3", "m4a", "wav", "ogg", "mp4", "mpeg", "webm", "avi", "mov", "flv", "wmv", "mkv",
        # archives/binaries
        "zip", "gz", "tgz", "bz2", "7z", "rar", "exe", "msi", "apk", "dmg", "iso",
        # docs
        "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "rtf",
        # code/packages
        "tar", "jar", "swf",
    }

    # Extensions commonly used for HTML-like dynamic pages that we allow
    _ALLOW_EXT = {"", "html", "htm", "xhtml", "php", "asp", "aspx", "phtml"}

    @staticmethod
    def _ext(url: str) -> str:
        try:
            path = urlparse(url).path
            if not path:
                return ""
            dot = path.rfind(".")
            if dot == -1:
                return ""
            # stop at non-alnum chars
            end = len(path)
            for i in range(dot + 1, len(path)):
                c = path[i]
                if not c.isalnum():
                    end = i
                    break
            return path[dot + 1:end].lower()
        except Exception:
            return ""

    def apply(self, url: str) -> bool:
        ext = self._ext(url)
        if ext in self._REJECT_EXT:
            return False
        # Allow empty/no extension and known HTML-like extensions
        return ext in self._ALLOW_EXT


@dataclass
class URLPatternFilter(URLFilter):
    """Include/exclude substring patterns.

    - Exclude patterns take precedence.
    - If `include_patterns` is provided (non-empty), require at least one include match.
    - If `include_patterns` is empty, default allow (subject to excludes).
    """

    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None

    def apply(self, url: str) -> bool:
        s = (url or "").lower()
        # Exclude wins
        if self.exclude_patterns:
            for p in self.exclude_patterns:
                if p and p.lower() in s:
                    return False
        # Include gating (optional)
        if self.include_patterns:
            for p in self.include_patterns:
                if p and p.lower() in s:
                    return True
            return False
        return True


class RobotsFilter:
    """Asynchronous robots.txt gate with per-domain cache.

    Notes:
    - This filter is not part of the synchronous FilterChain. Call `await allowed(url)` explicitly.
    - Fails open (allow) when robots.txt is unreachable or parser errors occur.
    - Honors centralized egress guard: robots check runs only for allowed hosts.
    """

    def __init__(
        self,
        user_agent: str,
        *,
        ttl_seconds: int = 1800,
        backend: str = "httpx",
        timeout: float = 5.0,
    ) -> None:
        self.user_agent = user_agent
        self.ttl_seconds = int(ttl_seconds)
        self.backend = backend
        self.timeout = float(timeout)
        # host -> (RobotFileParser|None, fetched_at_epoch_seconds)
        self._cache: Dict[str, Tuple[Optional[RobotFileParser], float]] = {}
        # Lock to avoid stampede on first fetch per host
        self._locks: Dict[str, asyncio.Lock] = {}

    def _robots_url_for(self, target_url: str) -> str:
        p = urlparse(target_url)
        return f"{p.scheme}://{p.netloc}/robots.txt"

    def _host(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    async def _fetch_parser(self, url: str) -> Optional[RobotFileParser]:
        host = self._host(url)
        if not host:
            return None

        # TTL-based cache
        now = time.time()
        cached = self._cache.get(host)
        if cached is not None:
            parser, ts = cached
            if (now - ts) < self.ttl_seconds:
                return parser

        # Ensure only one fetch in-flight per host
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            # Re-check after acquiring the lock
            cached = self._cache.get(host)
            if cached is not None:
                parser, ts = cached
                if (time.time() - ts) < self.ttl_seconds:
                    return parser

            robots_url = self._robots_url_for(url)
            try:
                if http_fetch is None:
                    logger.debug("http_fetch not available; allowing by default (no robots fetch)")
                    self._cache[host] = (None, time.time())
                    return None

                # Use thread offload to keep interface consistent with other code paths
                resp = await asyncio.to_thread(
                    http_fetch,
                    robots_url,
                    method="GET",
                    backend=self.backend,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                text = resp.get("text") if isinstance(resp, dict) else None
                status = resp.get("status") if isinstance(resp, dict) else None
                if not text or (isinstance(status, int) and status >= 400):
                    # Treat missing/unreadable robots as allow
                    self._cache[host] = (None, time.time())
                    return None
                rp = RobotFileParser()
                rp.parse(text.splitlines())
                self._cache[host] = (rp, time.time())
                return rp
            except Exception as e:  # pragma: no cover - network/parse errors fail open
                logger.debug(f"Robots fetch failed for host={host}: {e}")
                self._cache[host] = (None, time.time())
                return None

    async def allowed(self, url: str) -> bool:
        """Return True if URL passes robots policy or when check is skipped.

        Skips robots check when egress policy denies the target host.
        """
        try:
            # Always short-circuit on egress denial; do not fetch robots for disallowed hosts
            if evaluate_url_policy is not None:
                pol = evaluate_url_policy(url)
                if not getattr(pol, "allowed", False):
                    return False
        except Exception:
            # On egress evaluation error, fail closed for safety at enqueue time
            return False

        parser = await self._fetch_parser(url)
        if parser is None:
            # If fetcher not available, fall back to one-off async helper when present
            try:
                from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
                    is_allowed_by_robots_async as _robots_check_async,
                )
                return await _robots_check_async(url, self.user_agent, backend=self.backend, timeout=self.timeout)
            except Exception:
                # Fail open: treat as allowed when robots is missing/unreadable
                return True
        try:
            return bool(parser.can_fetch(self.user_agent, url))
        except Exception:
            return True
