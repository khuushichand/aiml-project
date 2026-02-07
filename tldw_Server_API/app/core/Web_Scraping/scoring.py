from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from urllib.parse import urlparse


class URLScorer:
    """Base scorer interface."""

    weight: float = 1.0

    def score(self, url: str) -> float:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class PathDepthScorer(URLScorer):
    optimal_depth: int = 3
    weight: float = 1.0

    @staticmethod
    @lru_cache(maxsize=10000)
    def _depth(url: str) -> int:
        try:
            p = urlparse(url)
            path = p.path or "/"
            if path == "/":
                return 0
            # Count non-empty segments
            return len([seg for seg in path.split('/') if seg])
        except Exception:
            return 0

    def score(self, url: str) -> float:
        d = self._depth(url)
        dist = abs(d - self.optimal_depth)
        base = 1.0 / (1.0 + float(dist))
        return base * self.weight


@dataclass
class KeywordRelevanceScorer(URLScorer):
    keywords: list[str]
    weight: float = 1.0

    def __post_init__(self) -> None:
        self._kw = [k.strip().lower() for k in (self.keywords or []) if k and k.strip()]

    @staticmethod
    @lru_cache(maxsize=10000)
    def _score_core_cached(keywords_key: tuple[str, ...], url_lower: str) -> float:
        if not keywords_key:
            return 0.0
        matches = sum(1 for k in keywords_key if k in url_lower)
        if matches <= 0:
            return 0.0
        return min(1.0, matches / float(len(keywords_key)))

    def score(self, url: str) -> float:
        kw_key = tuple(self._kw)
        return self._score_core_cached(kw_key, (url or "").lower()) * self.weight


@dataclass
class ContentTypeScorer(URLScorer):
    """Give preference to HTML-like paths."""

    weight: float = 1.0

    @staticmethod
    @lru_cache(maxsize=10000)
    def _ext(url: str) -> str:
        try:
            path = urlparse(url).path
            if not path:
                return ""
            dot = path.rfind('.')
            if dot == -1:
                return ""
            end = len(path)
            for i in range(dot + 1, len(path)):
                c = path[i]
                if not c.isalnum():
                    end = i
                    break
            return path[dot + 1:end].lower()
        except Exception:
            return ""

    def score(self, url: str) -> float:
        ext = self._ext(url)
        allow = {"", "html", "htm", "xhtml", "php", "asp", "aspx", "phtml"}
        base = 1.0 if ext in allow else 0.0
        return base * self.weight


@dataclass
class FreshnessScorer(URLScorer):
    weight: float = 1.0
    current_year: int | None = None

    def __post_init__(self) -> None:
        if self.current_year is None:
            self.current_year = datetime.now().year

    @staticmethod
    @lru_cache(maxsize=10000)
    def _extract_year_cached(url: str, current_year: int) -> int | None:
        """Extract the most recent <= current_year 4-digit year from URL path."""
        try:
            path = (urlparse(url).path or "").lower()
            import re
            years = [int(m.group(0)) for m in re.finditer(r"(?<!\d)(19|20)\d{2}(?!\d)", path)]
            return max((y for y in years if y <= int(current_year)), default=None)
        except Exception:
            return None

    def score(self, url: str) -> float:
        y = self._extract_year_cached(url, int(self.current_year))
        if y is None:
            return 0.5 * self.weight
        diff = max(0, int(self.current_year) - int(y))
        # 1.0 this year, then decay
        if diff == 0:
            base = 1.0
        elif diff == 1:
            base = 0.9
        elif diff == 2:
            base = 0.8
        elif diff == 3:
            base = 0.7
        elif diff == 4:
            base = 0.6
        elif diff == 5:
            base = 0.5
        else:
            base = max(0.1, 1.0 - 0.1 * diff)
        return base * self.weight


@dataclass
class DomainAuthorityScorer(URLScorer):
    domain_weights: dict[str, float]
    default_weight: float = 0.5
    weight: float = 1.0

    @staticmethod
    @lru_cache(maxsize=10000)
    def _domain(url: str) -> str:
        try:
            host = urlparse(url).netloc.lower()
            if ':' in host:
                host = host.split(':', 1)[0]
            return host
        except Exception:
            return ""

    def score(self, url: str) -> float:
        d = self._domain(url)
        s = self.domain_weights.get(d, self.default_weight)
        return s * self.weight


class CompositeScorer(URLScorer):
    def __init__(self, scorers: list[URLScorer], normalize: bool = True) -> None:
        self.scorers = scorers or []
        self.normalize = normalize
        self._cache: dict[str, float] = {}

    def score(self, url: str) -> float:
        if url in self._cache:
            return self._cache[url]
        total = 0.0
        for s in self.scorers:
            try:
                total += float(s.score(url))
            except Exception:
                # Robust to any single scorer failure
                pass
        if self.normalize and self.scorers:
            total /= float(len(self.scorers))
        self._cache[url] = total
        return total
