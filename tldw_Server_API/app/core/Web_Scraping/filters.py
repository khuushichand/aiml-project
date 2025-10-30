from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urlparse


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

