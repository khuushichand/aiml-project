# enhanced_web_scraping.py - Production Web Scraping Pipeline
"""
Enhanced web scraping pipeline with production features:
- Concurrent scraping with rate limiting (local and optional ResourceGovernor)
- Job queue management with priority
- Cookie/session management
- Progress tracking and resumability
- Content deduplication
- Robust error handling and retries
- Support for multiple scraping strategies

Persistent caches:
- Cookies and deduplication hashes are stored under `Databases/webscraper/`
  within the project root (created on demand) for durability and easier ops.
"""

import asyncio
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import pickle
from collections import deque, defaultdict
from urllib.parse import urlparse, urljoin
import random
import os
import re

from loguru import logger
import aiofiles
from bs4 import BeautifulSoup
import trafilatura
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import atexit
from heapq import heappush, heappop
#
# Import existing components
from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze
from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.Utils.Utils import get_database_dir
from tldw_Server_API.app.core.Web_Scraping.url_utils import normalize_for_crawl
from tldw_Server_API.app.core.Web_Scraping.scoring import (
    CompositeScorer,
    PathDepthScorer,
    KeywordRelevanceScorer,
    ContentTypeScorer as CTScorer,
    FreshnessScorer,
    DomainAuthorityScorer,
)
from tldw_Server_API.app.core.Web_Scraping.filters import (
    FilterChain,
    DomainFilter,
    ContentTypeFilter,
    URLPatternFilter,
    RobotsFilter,
)
from tldw_Server_API.app.core.Web_Scraping.scraper_router import ScraperRouter, DEFAULT_HANDLER
from tldw_Server_API.app.core.Web_Scraping.ua_profiles import build_browser_headers, profile_to_impersonate
from tldw_Server_API.app.core.Web_Scraping.handlers import resolve_handler
from tldw_Server_API.app.core.http_client import afetch
from tldw_Server_API.app.core.Metrics import increment_counter, observe_histogram
from tldw_Server_API.app.core.Metrics.metrics_logger import (
    log_counter,
    log_histogram,
    log_gauge,
)

# Optional Resource Governor integration (gated by global RG_ENABLED/config)
try:  # pragma: no cover - RG is optional
    from tldw_Server_API.app.core.Resource_Governance import (  # type: ignore
        MemoryResourceGovernor,
        RedisResourceGovernor,
        RGRequest,
    )
    from tldw_Server_API.app.core.Resource_Governance.policy_loader import (  # type: ignore
        PolicyLoader,
        PolicyReloadConfig,
        default_policy_loader,
    )
    from tldw_Server_API.app.core.config import rg_enabled  # type: ignore
except Exception:  # pragma: no cover - safe fallback when RG not installed
    MemoryResourceGovernor = None  # type: ignore
    RedisResourceGovernor = None  # type: ignore
    RGRequest = None  # type: ignore
    PolicyLoader = None  # type: ignore
    PolicyReloadConfig = None  # type: ignore
    default_policy_loader = None  # type: ignore
    rg_enabled = None  # type: ignore

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BEST_FIRST_BATCH_SIZE = 10


def _default_rules_path() -> str:
    here = Path(__file__).resolve()
    project_root = here.parents[3]
    return str(project_root / "tldw_Server_API" / "Config_Files" / "custom_scrapers.yaml")


class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class JobPriority(Enum):
    """Job priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ScrapingJob:
    """Represents a scraping job"""
    job_id: str
    url: str
    method: str
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retries: int = 0
    max_retries: int = 3
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            "job_id": self.job_id,
            "url": self.url,
            "method": self.method,
            "priority": self.priority.value,
            "status": self.status.name,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retries": self.retries,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }


class RateLimiter:
    """Rate limiting for scraping requests"""

    def __init__(self, max_requests_per_second: float = 2.0,
                 max_requests_per_minute: int = 60,
                 max_requests_per_hour: int = 1000):
        self.max_rps = max_requests_per_second
        self.max_rpm = max_requests_per_minute
        self.max_rph = max_requests_per_hour
        self._request_times: deque = deque(maxlen=max_requests_per_hour)
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire permission to make a request"""
        async with self._lock:
            rg_decision = await _maybe_enforce_with_rg_web_scraping()
            if rg_decision is not None and not rg_decision["allowed"]:
                retry_after = rg_decision.get("retry_after") or 1
                logger.info(
                    "Web scraping request delayed by ResourceGovernor: retry_after={}s",
                    retry_after,
                )
                # For scraping, we model RG denials as backoff rather than hard 429s.
                await asyncio.sleep(retry_after)

            now = time.time()

            # Clean old request times
            cutoff_hour = now - 3600
            while self._request_times and self._request_times[0] < cutoff_hour:
                self._request_times.popleft()

            # Check hourly limit
            if len(self._request_times) >= self.max_rph:
                wait_time = 3600 - (now - self._request_times[0])
                if wait_time > 0:
                    logger.info(f"Rate limit: waiting {wait_time:.1f}s for hourly limit")
                    await asyncio.sleep(wait_time)

            # Check minute limit
            minute_ago = now - 60
            recent_times = [t for t in self._request_times if t > minute_ago]
            recent_minute = len(recent_times)
            if recent_minute >= self.max_rpm:
                oldest_recent = min(recent_times) if recent_times else now
                wait_time = 60 - (now - oldest_recent)
                if wait_time > 0:
                    logger.info(f"Rate limit: waiting {wait_time:.1f}s for minute limit")
                    await asyncio.sleep(wait_time)

            # Check second limit
            if self._request_times and (now - self._request_times[-1]) < (1.0 / self.max_rps):
                wait_time = (1.0 / self.max_rps) - (now - self._request_times[-1])
                await asyncio.sleep(wait_time)

            # Record request time
            self._request_times.append(now)


_rg_web_governor = None
_rg_web_loader = None
_rg_web_lock = asyncio.Lock()


def _rg_web_scraping_enabled() -> bool:
    """Return True when RG should gate web scraping requests."""
    if rg_enabled is not None:
        try:
            return bool(rg_enabled(True))  # type: ignore[func-returns-value]
        except Exception:
            return False
    return False


async def _get_web_scraping_rg_governor():
    """Lazily initialize a ResourceGovernor instance for web scraping."""
    global _rg_web_governor, _rg_web_loader
    if not _rg_web_scraping_enabled():
        return None
    if RGRequest is None or PolicyLoader is None:
        return None
    if _rg_web_governor is not None:
        return _rg_web_governor
    async with _rg_web_lock:
        if _rg_web_governor is not None:
            return _rg_web_governor
        try:
            loader = (
                default_policy_loader()
                if default_policy_loader
                else PolicyLoader(
                    os.getenv(
                        "RG_POLICY_PATH",
                        "tldw_Server_API/Config_Files/resource_governor_policies.yaml",
                    ),
                    PolicyReloadConfig(
                        enabled=True,
                        interval_sec=int(
                            os.getenv("RG_POLICY_RELOAD_INTERVAL_SEC", "10") or "10"
                        ),
                    ),
                )
            )
            await loader.load_once()
            _rg_web_loader = loader
            backend = os.getenv("RG_BACKEND", "memory").lower()
            if backend == "redis" and RedisResourceGovernor is not None:
                gov = RedisResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            else:
                gov = MemoryResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            _rg_web_governor = gov
            return gov
        except Exception as exc:  # pragma: no cover - optional path
            logger.debug(
                "Web scraping RG governor init failed; using legacy RateLimiter: {}", exc
            )
            return None


async def _maybe_enforce_with_rg_web_scraping() -> Optional[Dict[str, object]]:
    """
    Optionally enforce web scraping request limits via ResourceGovernor.

    Returns a decision dict when RG is used, or None when RG is
    unavailable or disabled.
    """
    gov = await _get_web_scraping_rg_governor()
    if gov is None:
        return None
    policy_id = os.getenv("RG_WEB_SCRAPING_POLICY_ID", "web_scraping.default")
    op_id = f"web-scrape-{time.time_ns()}"
    try:
        decision, handle = await gov.reserve(
            RGRequest(
                entity="service:web_scraping",
                categories={"requests": {"units": 1}},
                tags={"policy_id": policy_id, "module": "web_scraping"},
            ),
            op_id=op_id,
        )
        if decision.allowed:
            if handle:
                try:
                    await gov.commit(handle, None, op_id=op_id)
                except Exception:
                    logger.debug("Web scraping RG commit failed", exc_info=True)
            return {"allowed": True, "retry_after": None, "policy_id": policy_id}
        return {
            "allowed": False,
            "retry_after": decision.retry_after or 1,
            "policy_id": policy_id,
        }
    except Exception as exc:
        logger.debug(
            "Web scraping RG reserve failed: {}", exc
        )
        return None


class CookieManager:
    """Manages cookies for scraping."""

    def __init__(self, storage_path: Optional[Path] = None, *, connector_limit: int = 10, per_host_limit: int = 2):
        if storage_path is None:
            base = Path(get_database_dir()) / "webscraper"
            base.mkdir(parents=True, exist_ok=True)
            storage_path = base / "cookies.json"
        self.storage_path = storage_path
        self._cookies: Dict[str, List[Dict[str, Any]]] = {}
        self._connector_limit = int(connector_limit)
        self._per_host_limit = int(per_host_limit)
        self._load_cookies()

    def _load_cookies(self):
        """Load cookies from storage"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    self._cookies = json.load(f)
                logger.info(f"Loaded cookies for {len(self._cookies)} domains")
            except Exception as e:
                logger.error(f"Failed to load cookies: {e}")

    def _save_cookies(self):
        """Save cookies to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self._cookies, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")

    def add_cookies(self, domain: str, cookies: List[Dict[str, Any]]):
        """Add cookies for a domain"""
        self._cookies[domain] = cookies
        self._save_cookies()

    def get_cookies(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """Get cookies for a URL"""
        domain = urlparse(url).netloc
        return self._cookies.get(domain)

    async def close_all(self):
        """No-op retained for backward compatibility."""
        return None


class ContentDeduplicator:
    """Handles content deduplication"""

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            base = Path(get_database_dir()) / "webscraper"
            base.mkdir(parents=True, exist_ok=True)
            storage_path = base / "content_hashes.pkl"
        self.storage_path = storage_path
        self._hashes: Dict[str, Dict[str, Any]] = {}
        self._load_hashes()

    def _load_hashes(self):
        """Load content hashes from storage"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'rb') as f:
                    self._hashes = pickle.load(f)
                logger.info(f"Loaded {len(self._hashes)} content hashes")
            except Exception as e:
                logger.error(f"Failed to load hashes: {e}")

    def _save_hashes(self):
        """Save content hashes to storage"""
        try:
            with open(self.storage_path, 'wb') as f:
                pickle.dump(self._hashes, f)
        except Exception as e:
            logger.error(f"Failed to save hashes: {e}")

    def compute_hash(self, content: str) -> str:
        """Compute hash for content"""
        # Normalize content before hashing
        normalized = ' '.join(content.lower().split())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def is_duplicate(self, url: str, content: str) -> bool:
        """Check if content is duplicate"""
        content_hash = self.compute_hash(content)

        # Check if exact hash exists
        if content_hash in self._hashes:
            existing = self._hashes[content_hash]
            if existing['url'] != url:
                logger.info(f"Duplicate content found: {url} duplicates {existing['url']}")
                return True

        return False

    def add_content(self, url: str, content: str, title: str = ""):
        """Add content hash to deduplication store"""
        content_hash = self.compute_hash(content)
        self._hashes[content_hash] = {
            "url": url,
            "title": title,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
        }
        self._save_hashes()

    def update_seen(self, content_hash: str):
        """Update last seen time for content"""
        if content_hash in self._hashes:
            self._hashes[content_hash]["last_seen"] = datetime.now().isoformat()
            self._save_hashes()

    def flush(self):
        """Force a save to disk"""
        try:
            self._save_hashes()
        except Exception as e:
            logger.error(f"Failed to flush content hashes: {e}")


class ScrapingJobQueue:
    """Priority job queue for scraping tasks"""

    def __init__(self, max_concurrent: int = 5, parent_scraper=None):
        self.max_concurrent = max_concurrent
        self.parent_scraper = parent_scraper  # Store reference to parent scraper
        self._queues: Dict[JobPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in JobPriority
        }
        self._active_jobs: Dict[str, ScrapingJob] = {}
        self._completed_jobs: Dict[str, ScrapingJob] = {}
        self._job_futures: Dict[str, asyncio.Future] = {}
        self._workers: List[asyncio.Task] = []
        self._shutdown = False
        self._lock = asyncio.Lock()

    async def start(self):
        """Start worker tasks"""
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)
        logger.info(f"Started {self.max_concurrent} scraping workers")

    async def stop(self):
        """Stop all workers"""
        self._shutdown = True

        # Cancel all pending jobs
        for queue in self._queues.values():
            while not queue.empty():
                try:
                    job = await queue.get()
                    job.status = JobStatus.CANCELLED
                    if job.job_id in self._job_futures:
                        self._job_futures[job.job_id].set_exception(
                            Exception("Job cancelled due to shutdown")
                        )
                except Exception as e:
                    logger.debug(f"Failed to cancel pending scraping job during shutdown: error={e}")

        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("All scraping workers stopped")

    async def add_job(self, job: ScrapingJob) -> asyncio.Future:
        """Add job to queue and return future for result"""
        async with self._lock:
            # Create future for job result
            future = asyncio.Future()
            self._job_futures[job.job_id] = future

            # Add to appropriate priority queue
            await self._queues[job.priority].put(job)
            logger.info(f"Added job {job.job_id} with priority {job.priority.name}")

            return future

    async def _worker(self, worker_id: str):
        """Worker task to process jobs"""
        logger.info(f"{worker_id} started")

        while not self._shutdown:
            job = None
            try:
                # Get highest priority job
                for priority in sorted(JobPriority, key=lambda p: p.value, reverse=True):
                    if not self._queues[priority].empty():
                        job = await asyncio.wait_for(
                            self._queues[priority].get(),
                            timeout=0.1
                        )
                        break

                if not job:
                    await asyncio.sleep(0.1)
                    continue

                # Process job
                async with self._lock:
                    job.status = JobStatus.IN_PROGRESS
                    job.started_at = datetime.now()
                    self._active_jobs[job.job_id] = job

                logger.info(f"{worker_id} processing job {job.job_id}")

                # Execute job (implement actual scraping logic)
                result = await self._execute_job(job)

                # Update job status
                async with self._lock:
                    job.completed_at = datetime.now()
                    if result.get("error"):
                        job.status = JobStatus.FAILED
                        job.error = result["error"]

                        # Retry if possible
                        if job.retries < job.max_retries:
                            job.retries += 1
                            job.status = JobStatus.PENDING
                            await self._queues[job.priority].put(job)
                            logger.info(f"Retrying job {job.job_id} ({job.retries}/{job.max_retries})")
                            continue
                    else:
                        job.status = JobStatus.COMPLETED
                        job.result = result

                    # Move to completed
                    del self._active_jobs[job.job_id]
                    self._completed_jobs[job.job_id] = job

                    # Resolve future
                    if job.job_id in self._job_futures:
                        if job.status == JobStatus.COMPLETED:
                            self._job_futures[job.job_id].set_result(job.result)
                        else:
                            self._job_futures[job.job_id].set_exception(
                                Exception(job.error or "Job failed")
                            )
                        del self._job_futures[job.job_id]

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"{worker_id} error: {e}")
                if job:
                    async with self._lock:
                        job.completed_at = datetime.now()
                        job.status = JobStatus.FAILED
                        job.error = str(e)
                        if job.job_id in self._active_jobs:
                            del self._active_jobs[job.job_id]
                        self._completed_jobs[job.job_id] = job
                        future = self._job_futures.pop(job.job_id, None)
                    if future and not future.done():
                        future.set_exception(e)

        logger.info(f"{worker_id} stopped")

    async def _execute_job(self, job: ScrapingJob) -> Dict[str, Any]:
        """Execute a scraping job"""
        # Get the scraper instance from parent
        if self.parent_scraper:
            # Use the parent scraper's actual scraping method
            return await self.parent_scraper.scrape_article(
                job.url,
                job.method,
                custom_cookies=job.metadata.get('custom_cookies'),
                user_agent=job.metadata.get('user_agent'),
                custom_headers=job.metadata.get('custom_headers')
            )
        else:
            # Fallback to importing the standalone scraping function
            logger.warning(f"No parent scraper available for job {job.job_id}, using fallback scraping")
            from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import scrape_article
            return await scrape_article(job.url, custom_cookies=job.metadata.get('custom_cookies'))

    def get_status(self) -> Dict[str, Any]:
        """Get queue status"""
        return {
            "active_jobs": len(self._active_jobs),
            "completed_jobs": len(self._completed_jobs),
            "pending_by_priority": {
                priority.name: self._queues[priority].qsize()
                for priority in JobPriority
            }
        }


class EnhancedWebScraper:
    """Main enhanced web scraping class"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Respect an explicitly provided (even empty) config; only fall back to
        # on-disk config when config is None.
        raw_cfg = config if config is not None else load_and_log_configs().get('web_scraper', {})
        # Normalize config values
        def _as_float(v, d):
            try:
                return float(v)
            except Exception:
                return float(d)
        def _as_int(v, d):
            try:
                return int(v)
            except Exception:
                return int(d)
        self.config = raw_cfg

        # Initialize components
        self.rate_limiter = RateLimiter(
            max_requests_per_second=_as_float(self.config.get('max_rps', 2.0), 2.0),
            max_requests_per_minute=_as_int(self.config.get('max_rpm', 60), 60),
            max_requests_per_hour=_as_int(self.config.get('max_rph', 1000), 1000)
        )
        connector_limit = _as_int(self.config.get('connector_limit', 10), 10)
        per_host_limit = _as_int(self.config.get('connector_limit_per_host', 2), 2)
        self.cookie_manager = CookieManager(connector_limit=connector_limit, per_host_limit=per_host_limit)
        self.deduplicator = ContentDeduplicator()
        self.job_queue = ScrapingJobQueue(
            max_concurrent=_as_int(self.config.get('max_concurrent', 5), 5),
            parent_scraper=self  # Pass self reference to job queue
        )

        # Playwright browser
        self._browser: Optional[Browser] = None
        self._playwright = None

        # Progress tracking
        self._progress: Dict[str, Any] = defaultdict(dict)

    @staticmethod
    def _as_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "y"}
        return default

    @staticmethod
    def _normalize_cookie_map(
        custom_cookies: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, str]:
        cookies_map: Dict[str, str] = {}
        if not custom_cookies:
            return cookies_map
        for cookie in custom_cookies:
            if not isinstance(cookie, dict):
                continue
            if "name" in cookie and "value" in cookie:
                cookies_map[str(cookie["name"])] = str(cookie["value"])
            else:
                for key, value in cookie.items():
                    cookies_map[str(key)] = str(value)
        return cookies_map

    @staticmethod
    def _merge_cookie_maps(
        custom_cookies: Optional[List[Dict[str, Any]]],
        plan_cookies: Optional[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        merged = EnhancedWebScraper._normalize_cookie_map(custom_cookies)
        if plan_cookies:
            merged.update({str(k): str(v) for k, v in plan_cookies.items()})
        return [{"name": k, "value": v} for k, v in merged.items()]

    @staticmethod
    def _normalize_playwright_cookies(
        url: str,
        custom_cookies: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        cookies_list: List[Dict[str, Any]] = []
        if not custom_cookies:
            return cookies_list
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else url
        for cookie in custom_cookies:
            if not isinstance(cookie, dict):
                continue
            if "name" in cookie and "value" in cookie:
                cookies_list.append(
                    {
                        "name": str(cookie["name"]),
                        "value": str(cookie["value"]),
                        "url": base_url,
                    }
                )
            else:
                for key, value in cookie.items():
                    cookies_list.append(
                        {
                            "name": str(key),
                            "value": str(value),
                            "url": base_url,
                        }
                    )
        return cookies_list

    @staticmethod
    def _parse_proxy_for_playwright(proxy_url: str) -> Optional[Dict[str, str]]:
        if not proxy_url:
            return None
        pattern = r"^(?:(?P<scheme>\\w+)://)?(?:(?P<username>[^:@]+):(?P<password>[^@]+)@)?(?P<host>[^:]+):(?P<port>\\d+)$"
        match = re.match(pattern, proxy_url)
        if not match:
            return None
        scheme = match.group("scheme") or "http"
        host = match.group("host")
        port = match.group("port")
        if not host or not port:
            return None
        result: Dict[str, str] = {"server": f"{scheme}://{host}:{port}"}
        username = match.group("username")
        password = match.group("password")
        if username and password:
            result["username"] = username
            result["password"] = password
        return result

    @staticmethod
    def _build_request_headers(
        user_agent: Optional[str],
        custom_headers: Optional[Dict[str, str]],
    ) -> Dict[str, str]:
        header_copy = dict(custom_headers) if custom_headers else {}
        effective_user_agent = user_agent or header_copy.pop("User-Agent", None) or DEFAULT_USER_AGENT
        headers = {"User-Agent": effective_user_agent}
        if header_copy:
            headers.update(header_copy)
        return headers

    @staticmethod
    def _build_plan_headers(
        ua_profile: str,
        plan_headers: Optional[Dict[str, str]],
        user_agent: Optional[str],
        custom_headers: Optional[Dict[str, str]],
    ) -> Dict[str, str]:
        headers = build_browser_headers(ua_profile, accept_lang="en-US,en;q=0.9")
        if plan_headers:
            headers.update({str(k): str(v) for k, v in plan_headers.items()})
        if custom_headers:
            headers.update({str(k): str(v) for k, v in custom_headers.items()})
        if user_agent:
            headers["User-Agent"] = user_agent
        return headers

    async def _run_preflight_analysis(self, url: str) -> Optional[Dict[str, Any]]:
        cfg = self.config or {}
        enabled = self._as_bool(cfg.get("web_scraper_preflight_analyzers", False), False)
        if not enabled:
            return None

        find_all = self._as_bool(cfg.get("web_scraper_preflight_find_all_waf", False), False)
        impersonate = self._as_bool(cfg.get("web_scraper_preflight_impersonate", False), False)
        scan_depth_raw = str(cfg.get("web_scraper_preflight_scan_depth", "") or "").strip().lower()
        if scan_depth_raw not in {"default", "thorough", "deep"}:
            scan_depth_raw = "default"

        try:
            timeout_s = float(cfg.get("web_scraper_preflight_timeout_s", 0) or 0)
        except Exception:
            timeout_s = 0.0

        try:
            from tldw_Server_API.app.core.Web_Scraping.scraper_analyzers import run_analysis

            task = asyncio.to_thread(
                run_analysis,
                url,
                find_all=find_all,
                impersonate=impersonate,
                scan_depth=scan_depth_raw,
            )
            if timeout_s and timeout_s > 0:
                return await asyncio.wait_for(task, timeout=timeout_s)
            return await task
        except asyncio.TimeoutError:
            logger.debug(f"Preflight analysis timed out for {url}")
            return None
        except Exception as exc:
            logger.debug(f"Preflight analysis failed for {url}: {exc}")
            return None

    @staticmethod
    def _apply_preflight_advice(
        preflight: Optional[Dict[str, Any]],
        backend_choice: str,
        method: str,
        backend_setting: str,
    ) -> Tuple[str, str, List[str]]:
        notes: List[str] = []
        if not preflight or not isinstance(preflight, dict):
            return backend_choice, method, notes

        results = preflight.get("results", {})
        if isinstance(results, dict):
            js_result = results.get("js", {}) or {}
            if (
                method == "auto"
                and js_result.get("status") == "success"
                and (js_result.get("js_required") or js_result.get("is_spa"))
            ):
                method = "playwright"
                notes.append("js_required")

            tls_result = results.get("tls", {}) or {}
            if backend_setting == "auto" and tls_result.get("status") == "active":
                backend_choice = "curl"
                notes.append("tls_active")

        return backend_choice, method, notes

    def _build_cookie_map(
        self,
        url: str,
        custom_cookies: Optional[List[Dict[str, Any]]],
    ) -> Optional[Dict[str, str]]:
        cookies: Dict[str, str] = {}
        stored = self.cookie_manager.get_cookies(url)
        if stored:
            cookies.update(self._normalize_cookie_map(stored))
        custom_map = self._normalize_cookie_map(custom_cookies)
        if custom_map:
            cookies.update(custom_map)
        return cookies or None

    def _resolve_scrape_plan(self, url: str) -> Tuple[Dict[str, Any], str, str]:
        ws_cfg = self.config or {}
        rules_path = ws_cfg.get("custom_scrapers_yaml_path", _default_rules_path())
        rules = ScraperRouter.load_rules_from_yaml(rules_path)
        ua_mode = str(ws_cfg.get("web_scraper_ua_mode", "fixed") or "fixed")
        respect_robots_default = ws_cfg.get("web_scraper_respect_robots", True)
        if isinstance(respect_robots_default, str):
            respect_robots_default = respect_robots_default.strip().lower() in {"1", "true", "yes", "on"}
        router = ScraperRouter(rules, ua_mode=ua_mode, default_respect_robots=bool(respect_robots_default))
        plan = router.resolve(url)

        backend_choice = str(getattr(plan, "backend", "auto") or "auto").lower().strip()
        if backend_choice not in {"auto", "curl", "httpx", "playwright"}:
            backend_choice = "auto"
        if backend_choice == "auto":
            default_backend = ws_cfg.get("web_scraper_default_backend")
            if isinstance(default_backend, str):
                backend_choice = default_backend.lower().strip() or "auto"
                if backend_choice not in {"auto", "curl", "httpx", "playwright"}:
                    backend_choice = "auto"

        handler_path = str(getattr(plan, "handler", "") or "")
        return plan, backend_choice, handler_path

    def _apply_dedup(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get("extraction_successful"):
            return data
        content = data.get("content", "") or ""
        title = data.get("title", "") or ""
        if self.deduplicator.is_duplicate(url, content):
            return {
                "url": url,
                "error": "Duplicate content",
                "extraction_successful": False,
                "is_duplicate": True,
            }
        self.deduplicator.add_content(url, content, title)
        return data

    def _emit_scrape_metrics(
        self,
        *,
        backend: str,
        outcome: str,
        elapsed_s: Optional[float] = None,
        content: Optional[str] = None,
    ) -> None:
        try:
            if elapsed_s is not None:
                observe_histogram("scrape_fetch_latency_seconds", elapsed_s, labels={"backend": backend})
        except Exception:
            pass
        try:
            increment_counter("scrape_fetch_total", labels={"backend": backend, "outcome": outcome})
        except Exception:
            pass
        if outcome == "success" and content:
            try:
                observe_histogram(
                    "scrape_content_length_bytes",
                    len(content.encode("utf-8", errors="ignore")),
                    labels={"backend": backend},
                )
            except Exception:
                pass

    def _extract_from_html_with_pipeline(
        self,
        html: str,
        url: str,
        *,
        strategy_order: Optional[List[str]] = None,
        handler: Optional[Any] = None,
        postprocess_markdown: bool = False,
        method_label: str = "trafilatura",
        fallback_extractor: Optional[Callable[[str, str], Dict[str, Any]]] = None,
        schema_rules: Optional[Dict[str, Any]] = None,
        llm_settings: Optional[Dict[str, Any]] = None,
        regex_settings: Optional[Dict[str, Any]] = None,
        cluster_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
            convert_html_to_markdown,
            extract_article_with_pipeline,
        )

        data = extract_article_with_pipeline(
            html,
            url,
            strategy_order=strategy_order,
            handler=handler,
            fallback_extractor=fallback_extractor,
            schema_rules=schema_rules,
            llm_settings=llm_settings,
            regex_settings=regex_settings,
            cluster_settings=cluster_settings,
        )
        if postprocess_markdown and data.get("extraction_successful") and data.get("content"):
            data["content"] = convert_html_to_markdown(data["content"])
        data.setdefault("method", method_label)
        return data

    async def _fetch_html(
        self,
        url: str,
        *,
        headers: Dict[str, str],
        cookies: Optional[Dict[str, str]],
        backend: str,
        impersonate: Optional[str],
        proxies: Optional[Dict[str, str]],
    ) -> Tuple[str, str, float]:
        if backend == "curl":
            try:
                t0 = time.time()
                html = await asyncio.to_thread(
                    self._fetch_html_curl,
                    url,
                    headers=headers,
                    cookies=cookies,
                    timeout=15.0,
                    impersonate=impersonate,
                    proxies=proxies,
                )
                elapsed = max(0.0, time.time() - t0)
                return html, "curl", elapsed
            except Exception as exc:
                logger.debug(f"curl backend failed; falling back to httpx: {exc}")
        t0 = time.time()
        resp = None
        try:
            resp = await afetch(
                method="GET",
                url=url,
                headers=headers,
                cookies=cookies,
                proxies=proxies,
            )
        finally:
            await self._close_response(resp)
        backend_used = "httpx"
        try:
            module_name = getattr(resp, "__class__", type(resp)).__module__ or ""
            if module_name.startswith("aiohttp"):
                backend_used = "aiohttp"
        except Exception:
            backend_used = "httpx"
        return resp.text, backend_used, max(0.0, time.time() - t0)

    @staticmethod
    def _fetch_html_curl(
        url: str,
        *,
        headers: Dict[str, str],
        cookies: Optional[Dict[str, str]],
        timeout: float,
        impersonate: Optional[str],
        proxies: Optional[Dict[str, str]],
    ) -> str:
        try:
            from curl_cffi.requests import Session as CurlCffiSession
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("curl_cffi is not installed") from exc

        if proxies:
            from tldw_Server_API.app.core import http_client as _http_client
            _http_client._validate_proxies_or_raise(proxies)  # type: ignore[attr-defined]

        req_kwargs: Dict[str, Any] = {
            "headers": headers,
            "cookies": cookies,
            "timeout": timeout,
        }
        if proxies:
            req_kwargs["proxies"] = proxies

        with CurlCffiSession(impersonate=impersonate) as session:
            resp = session.get(url, **req_kwargs)
            return resp.text

    @staticmethod
    async def _close_response(resp: Any) -> None:
        if resp is None:
            return
        close = getattr(resp, "aclose", None)
        if callable(close):
            await close()
            return
        close = getattr(resp, "close", None)
        if callable(close):
            close()

    def _set_progress(self, task_id: Optional[str], **updates: Any) -> None:
        if not task_id:
            return
        entry = dict(self._progress.get(task_id, {}))
        entry.update(updates)
        entry["updated_at"] = datetime.now().isoformat()
        self._progress[task_id] = entry

    async def start(self):
        """Start the scraper"""
        await self.job_queue.start()

        try:
            # Initialize Playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            logger.info("Playwright browser initialized successfully")
        except ImportError:
            logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")
            logger.warning("Web scraping will proceed without JavaScript rendering support")
            self._playwright = None
            self._browser = None
        except Exception as e:
            logger.error(f"Failed to initialize Playwright browser: {e}")
            logger.warning("Web scraping will proceed without JavaScript rendering support")
            self._playwright = None
            self._browser = None

        # Ensure dedup flush on process exit
        atexit.register(lambda: self.deduplicator.flush())
        logger.info("Enhanced web scraper started")

    async def stop(self):
        """Stop the scraper"""
        await self.job_queue.stop()
        await self.cookie_manager.close_all()

        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        # Final flush
        self.deduplicator.flush()

        logger.info("Enhanced web scraper stopped")

    async def scrape_article(
        self,
        url: str,
        method: str = "auto",
        custom_cookies: Optional[List[Dict[str, Any]]] = None,
        user_agent: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Scrape a single article with specified method"""
        # Enforce centralized egress/SSRF policy before any network access
        try:
            from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
            pol = evaluate_url_policy(url)
            if not getattr(pol, 'allowed', False):
                return {
                    "url": url,
                    "error": f"Egress denied: {getattr(pol, 'reason', 'blocked')}",
                    "extraction_successful": False,
                }
        except Exception as _e:
            return {
                "url": url,
                "error": f"Egress policy evaluation failed: {_e}",
                "extraction_successful": False,
            }
        # Apply rate limiting
        await self.rate_limiter.acquire()

        try:
            plan, backend_choice, handler_path = self._resolve_scrape_plan(url)
            handler_path = str(handler_path or "")
            is_default_handler = (not handler_path) or handler_path == DEFAULT_HANDLER
            handler_func = resolve_handler(handler_path) if not is_default_handler else None
            strategy_order = getattr(plan, "strategy_order", None)
            schema_rules = getattr(plan, "schema_rules", None)
            llm_settings = getattr(plan, "llm_settings", None)
            regex_settings = getattr(plan, "regex_settings", None)
            cluster_settings = getattr(plan, "cluster_settings", None)
            postprocess_markdown = is_default_handler

            merged_cookies = self._merge_cookie_maps(custom_cookies, getattr(plan, "cookies", {}))
            headers = self._build_plan_headers(
                getattr(plan, "ua_profile", "chrome_120_win"),
                getattr(plan, "extra_headers", {}),
                user_agent,
                custom_headers,
            )
            if backend_choice in {"httpx", "auto"}:
                try:
                    from tldw_Server_API.app.core import http_client as _http_client
                    headers = _http_client._sanitize_accept_encoding_for_backend(headers, "httpx")  # type: ignore[attr-defined]
                except Exception:
                    pass

            preflight_analysis = await self._run_preflight_analysis(url)
            backend_setting = str(getattr(plan, "backend", "auto") or "auto").lower()
            backend_choice, method, preflight_notes = self._apply_preflight_advice(
                preflight_analysis, backend_choice, method, backend_setting
            )
            if preflight_notes:
                logger.debug(f"Preflight advice for {url}: {preflight_notes}")

            include_preflight = self._as_bool(
                (self.config or {}).get("web_scraper_preflight_include_results", False),
                False,
            )
            preflight_payload = None
            if include_preflight and preflight_analysis is not None:
                preflight_payload = {
                    "analysis": preflight_analysis,
                    "advice": {
                        "backend": backend_choice,
                        "method": method,
                        "notes": preflight_notes,
                    },
                }

            def _attach_preflight(result: Dict[str, Any]) -> Dict[str, Any]:
                if preflight_payload and isinstance(result, dict):
                    result.setdefault("preflight_analysis", preflight_payload)
                return result

            # robots.txt enforcement (fail open if error)
            if getattr(plan, "respect_robots", True):
                try:
                    from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
                        is_allowed_by_robots_async,
                    )
                    if not await is_allowed_by_robots_async(url, headers.get("User-Agent", DEFAULT_USER_AGENT)):
                        try:
                            parsed = urlparse(url)
                            increment_counter("scrape_blocked_by_robots_total", labels={"domain": parsed.netloc})
                        except Exception:
                            increment_counter("scrape_blocked_by_robots_total", labels={})
                        return _attach_preflight({
                            "url": url,
                            "error": "Blocked by robots policy",
                            "extraction_successful": False,
                        })
                except Exception:
                    pass

            effective_method = method
            if backend_choice == "playwright":
                effective_method = "playwright"
            elif effective_method == "auto":
                effective_method = "trafilatura"

            if effective_method == "trafilatura":
                result = await self._scrape_with_trafilatura(
                    url,
                    merged_cookies,
                    user_agent=None,
                    custom_headers=headers,
                    backend=backend_choice,
                    impersonate=getattr(plan, "impersonate", profile_to_impersonate(getattr(plan, "ua_profile", ""))),
                    proxies=getattr(plan, "proxies", None),
                    handler=handler_func,
                    strategy_order=strategy_order,
                    postprocess_markdown=postprocess_markdown,
                    schema_rules=schema_rules,
                    llm_settings=llm_settings,
                    regex_settings=regex_settings,
                    cluster_settings=cluster_settings,
                )
                return _attach_preflight(result)
            elif effective_method == "playwright":
                result = await self._scrape_with_playwright(
                    url,
                    merged_cookies,
                    user_agent=None,
                    custom_headers=headers,
                    proxies=getattr(plan, "proxies", None),
                    handler=handler_func,
                    strategy_order=strategy_order,
                    postprocess_markdown=postprocess_markdown,
                    schema_rules=schema_rules,
                    llm_settings=llm_settings,
                    regex_settings=regex_settings,
                    cluster_settings=cluster_settings,
                )
                return _attach_preflight(result)
            elif effective_method == "beautifulsoup":
                result = await self._scrape_with_beautifulsoup(
                    url,
                    merged_cookies,
                    user_agent=None,
                    custom_headers=headers,
                    backend=backend_choice,
                    impersonate=getattr(plan, "impersonate", profile_to_impersonate(getattr(plan, "ua_profile", ""))),
                    proxies=getattr(plan, "proxies", None),
                    handler=handler_func,
                    strategy_order=strategy_order,
                    postprocess_markdown=postprocess_markdown,
                    schema_rules=schema_rules,
                    llm_settings=llm_settings,
                    regex_settings=regex_settings,
                    cluster_settings=cluster_settings,
                )
                return _attach_preflight(result)
            else:
                raise ValueError(f"Unknown scraping method: {effective_method}")

        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return {
                "url": url,
                "error": str(e),
                "extraction_successful": False
            }

    async def _scrape_with_trafilatura(
        self,
        url: str,
        custom_cookies: Optional[List[Dict[str, Any]]] = None,
        user_agent: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        backend: str = "httpx",
        impersonate: Optional[str] = None,
        proxies: Optional[Dict[str, str]] = None,
        handler: Optional[Any] = None,
        strategy_order: Optional[List[str]] = None,
        postprocess_markdown: bool = False,
        schema_rules: Optional[Dict[str, Any]] = None,
        llm_settings: Optional[Dict[str, Any]] = None,
        regex_settings: Optional[Dict[str, Any]] = None,
        cluster_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Scrape using trafilatura"""
        headers = self._build_request_headers(user_agent, custom_headers)
        cookies = self._build_cookie_map(url, custom_cookies)
        effective_backend = backend if backend in {"curl", "httpx"} else "httpx"
        try:
            from tldw_Server_API.app.core import http_client as _http_client
            headers = _http_client._sanitize_accept_encoding_for_backend(headers, effective_backend)  # type: ignore[attr-defined]
        except Exception:
            pass
        t0 = time.time()
        try:
            html, backend_used, elapsed = await self._fetch_html(
                url,
                headers=headers,
                cookies=cookies,
                backend=effective_backend,
                impersonate=impersonate,
                proxies=proxies,
            )
        except Exception as exc:
            elapsed = max(0.0, time.time() - t0)
            self._emit_scrape_metrics(
                backend=effective_backend,
                outcome="error",
                elapsed_s=elapsed,
            )
            return {"url": url, "error": str(exc), "extraction_successful": False}

        data = self._extract_from_html_with_pipeline(
            html,
            url,
            strategy_order=strategy_order,
            handler=handler,
            postprocess_markdown=postprocess_markdown,
            method_label="trafilatura",
            fallback_extractor=self._extract_trafilatura_json,
            schema_rules=schema_rules,
            llm_settings=llm_settings,
            regex_settings=regex_settings,
            cluster_settings=cluster_settings,
        )
        outcome = "success" if data.get("extraction_successful") else "no_extract"
        self._emit_scrape_metrics(
            backend=backend_used,
            outcome=outcome,
            elapsed_s=elapsed,
            content=data.get("content") if outcome == "success" else None,
        )
        return self._apply_dedup(url, data)

    def _extract_trafilatura_json(self, html: str, url: str) -> Dict[str, Any]:
        """Extract using trafilatura JSON output to preserve legacy enhanced behavior."""
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_images=False,
            output_format='json',
        )

        if content:
            try:
                content_dict = json.loads(content)
            except json.JSONDecodeError as exc:
                return {
                    "url": url,
                    "error": f"Invalid trafilatura JSON: {exc}",
                    "extraction_successful": False,
                }

            return {
                "url": url,
                "title": content_dict.get('title', 'Untitled'),
                "author": content_dict.get('author', 'Unknown'),
                "date": content_dict.get('date', ''),
                "content": content_dict.get('text', ''),
                "extraction_successful": True,
                "method": "trafilatura",
            }

        return {
            "url": url,
            "error": "No content extracted",
            "extraction_successful": False,
        }

    async def _scrape_with_playwright(
        self,
        url: str,
        custom_cookies: Optional[List[Dict[str, Any]]] = None,
        user_agent: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        proxies: Optional[Dict[str, str]] = None,
        handler: Optional[Any] = None,
        strategy_order: Optional[List[str]] = None,
        postprocess_markdown: bool = False,
        schema_rules: Optional[Dict[str, Any]] = None,
        llm_settings: Optional[Dict[str, Any]] = None,
        regex_settings: Optional[Dict[str, Any]] = None,
        cluster_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Scrape using Playwright for JavaScript-heavy sites"""
        # Fallback gracefully if browser isn't initialized
        if not self._browser:
            return await self._scrape_with_trafilatura(
                url,
                custom_cookies=custom_cookies,
                user_agent=user_agent,
                custom_headers=custom_headers,
                handler=handler,
                strategy_order=strategy_order,
                postprocess_markdown=postprocess_markdown,
                schema_rules=schema_rules,
                llm_settings=llm_settings,
                regex_settings=regex_settings,
                cluster_settings=cluster_settings,
            )
        headers_copy = dict(custom_headers) if custom_headers else {}
        effective_user_agent = user_agent or headers_copy.pop("User-Agent", None) or DEFAULT_USER_AGENT

        proxy_cfg = None
        if proxies:
            try:
                from tldw_Server_API.app.core import http_client as _http_client
                _http_client._validate_proxies_or_raise(proxies)  # type: ignore[attr-defined]
                proxy_server = _http_client._resolve_proxy_for_url(url, proxies)  # type: ignore[attr-defined]
                if proxy_server:
                    proxy_cfg = self._parse_proxy_for_playwright(proxy_server)
                    if proxy_cfg is None:
                        if "://" in proxy_server:
                            proxy_cfg = {"server": proxy_server}
                        else:
                            proxy_cfg = {"server": f"http://{proxy_server}"}
            except Exception as exc:
                logger.debug(f"Playwright proxy validation failed: {exc}")

        if proxy_cfg:
            context = await self._browser.new_context(user_agent=effective_user_agent, proxy=proxy_cfg)
        else:
            context = await self._browser.new_context(user_agent=effective_user_agent)

        if headers_copy:
            await context.set_extra_http_headers(headers_copy)

        pw_cookies = self._normalize_playwright_cookies(url, custom_cookies)
        if pw_cookies:
            await context.add_cookies(pw_cookies)

        page = await context.new_page()
        t0 = time.time()

        try:
            # Navigate with timeout
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for content to load
            await page.wait_for_load_state("domcontentloaded")

            html = await page.content()
            data = self._extract_from_html_with_pipeline(
                html,
                url,
                strategy_order=strategy_order,
                handler=handler,
                postprocess_markdown=postprocess_markdown,
                method_label="playwright",
                fallback_extractor=self._extract_trafilatura_json,
                schema_rules=schema_rules,
                llm_settings=llm_settings,
                regex_settings=regex_settings,
                cluster_settings=cluster_settings,
            )
            if data.get("extraction_successful") or handler is not None:
                outcome = "success" if data.get("extraction_successful") else "no_extract"
                elapsed = max(0.0, time.time() - t0)
                self._emit_scrape_metrics(
                    backend="playwright",
                    outcome=outcome,
                    elapsed_s=elapsed,
                    content=data.get("content") if outcome == "success" else None,
                )
                return self._apply_dedup(url, data)
            pipeline_trace = data.get("extraction_trace") if isinstance(data.get("extraction_trace"), list) else []

            # Extract content (Playwright fallback)
            title = await page.title()

            # Try to find main content
            content = ""
            for selector in ['main', 'article', '[role="main"]', '#content', '.content']:
                elements = await page.query_selector_all(selector)
                if elements:
                    for element in elements:
                        text = await element.inner_text()
                        if len(text) > len(content):
                            content = text

            # Fallback to body if no content found
            if not content:
                content = await page.inner_text('body')

            # Extract metadata
            author = await page.evaluate('''() => {
                const meta = document.querySelector('meta[name="author"]');
                return meta ? meta.content : "Unknown";
            }''')

            date = await page.evaluate('''() => {
                const meta = document.querySelector('meta[property="article:published_time"]');
                return meta ? meta.content : "";
            }''')

            data = {
                "url": url,
                "title": title,
                "author": author,
                "date": date,
                "content": content,
                "extraction_successful": True,
                "method": "playwright"
            }
            trace = list(pipeline_trace)
            trace.append({"strategy": "playwright", "status": "success", "reason": "fallback_extracted"})
            data["extraction_trace"] = trace
            data["extraction_strategy"] = "playwright"
            data.setdefault("extraction_strategy_order", ["playwright"])
            log_counter("extraction_strategy_total", labels={"strategy": "playwright", "status": "success"})
            elapsed = max(0.0, time.time() - t0)
            self._emit_scrape_metrics(
                backend="playwright",
                outcome="success",
                elapsed_s=elapsed,
                content=content,
            )
            return self._apply_dedup(url, data)

        except Exception as exc:
            elapsed = max(0.0, time.time() - t0)
            self._emit_scrape_metrics(
                backend="playwright",
                outcome="error",
                elapsed_s=elapsed,
            )
            return {"url": url, "error": str(exc), "extraction_successful": False}

        finally:
            await page.close()
            await context.close()

    async def _scrape_with_beautifulsoup(
        self,
        url: str,
        custom_cookies: Optional[List[Dict[str, Any]]] = None,
        user_agent: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        backend: str = "httpx",
        impersonate: Optional[str] = None,
        proxies: Optional[Dict[str, str]] = None,
        handler: Optional[Any] = None,
        strategy_order: Optional[List[str]] = None,
        postprocess_markdown: bool = False,
        schema_rules: Optional[Dict[str, Any]] = None,
        llm_settings: Optional[Dict[str, Any]] = None,
        regex_settings: Optional[Dict[str, Any]] = None,
        cluster_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Scrape using BeautifulSoup for simple HTML parsing"""
        headers = self._build_request_headers(user_agent, custom_headers)
        cookies = self._build_cookie_map(url, custom_cookies)
        effective_backend = backend if backend in {"curl", "httpx"} else "httpx"
        try:
            from tldw_Server_API.app.core import http_client as _http_client
            headers = _http_client._sanitize_accept_encoding_for_backend(headers, effective_backend)  # type: ignore[attr-defined]
        except Exception:
            pass
        t0 = time.time()
        try:
            html, backend_used, elapsed = await self._fetch_html(
                url,
                headers=headers,
                cookies=cookies,
                backend=effective_backend,
                impersonate=impersonate,
                proxies=proxies,
            )
        except Exception as exc:
            elapsed = max(0.0, time.time() - t0)
            self._emit_scrape_metrics(
                backend=effective_backend,
                outcome="error",
                elapsed_s=elapsed,
            )
            return {"url": url, "error": str(exc), "extraction_successful": False}

        data = self._extract_from_html_with_pipeline(
            html,
            url,
            strategy_order=strategy_order,
            handler=handler,
            postprocess_markdown=postprocess_markdown,
            method_label="beautifulsoup",
            fallback_extractor=self._extract_trafilatura_json,
            schema_rules=schema_rules,
            llm_settings=llm_settings,
            regex_settings=regex_settings,
            cluster_settings=cluster_settings,
        )
        if data.get("extraction_successful") or handler is not None:
            outcome = "success" if data.get("extraction_successful") else "no_extract"
            self._emit_scrape_metrics(
                backend=backend_used,
                outcome=outcome,
                elapsed_s=elapsed,
                content=data.get("content") if outcome == "success" else None,
            )
            return self._apply_dedup(url, data)
        pipeline_trace = data.get("extraction_trace") if isinstance(data.get("extraction_trace"), list) else []
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"
        if not title:
            title = "Untitled"

        # Extract content
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Try to find main content
        content = ""
        for tag in ['main', 'article', 'div']:
            elements = soup.find_all(tag, class_=lambda x: x and any(
                keyword in x.lower() for keyword in ['content', 'article', 'post', 'entry']
            ))
            if elements:
                content = '\n\n'.join(elem.get_text(strip=True) for elem in elements)
                break

        # Fallback to body
        if not content:
            content = soup.get_text(strip=True)

        # Extract metadata
        author_meta = soup.find('meta', {'name': 'author'})
        author = author_meta.get('content', 'Unknown') if author_meta else 'Unknown'

        date_meta = soup.find('meta', {'property': 'article:published_time'})
        date = date_meta.get('content', '') if date_meta else ''

        data = {
            "url": url,
            "title": title,
            "author": author,
            "date": date,
            "content": content,
            "extraction_successful": True,
            "method": "beautifulsoup"
        }
        trace = list(pipeline_trace)
        trace.append({"strategy": "beautifulsoup", "status": "success", "reason": "fallback_extracted"})
        data["extraction_trace"] = trace
        data["extraction_strategy"] = "beautifulsoup"
        data.setdefault("extraction_strategy_order", ["beautifulsoup"])
        log_counter("extraction_strategy_total", labels={"strategy": "beautifulsoup", "status": "success"})
        self._emit_scrape_metrics(
            backend=backend_used,
            outcome="success",
            elapsed_s=elapsed,
            content=content,
        )
        return self._apply_dedup(url, data)

    async def scrape_multiple(self, urls: List[str], method: str = "auto",
                            priority: JobPriority = JobPriority.NORMAL,
                            summarize: bool = False,
                            **kwargs) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently"""
        jobs = []
        futures = []

        # Create jobs
        for url in urls:
            job = ScrapingJob(
                job_id=f"job_{int(time.time() * 1000)}_{hash(url)}",
                url=url,
                method=method,
                priority=priority,
                metadata=kwargs
            )
            future = await self.job_queue.add_job(job)
            jobs.append(job)
            futures.append(future)

        # Wait for all jobs to complete
        results = await asyncio.gather(*futures, return_exceptions=True)

        # Process results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "url": urls[i],
                    "error": str(result),
                    "extraction_successful": False
                })
            else:
                # Add summarization if requested
                if summarize and result.get('extraction_successful') and result.get('content'):
                    summary = await self._summarize_content(
                        result['content'],
                        **kwargs
                    )
                    result['summary'] = summary

                final_results.append(result)

        return final_results

    async def _summarize_content(self, content: str, **kwargs) -> str:
        """Summarize content using LLM"""
        try:
            summary = analyze(
                input_data=content,
                custom_prompt_arg=kwargs.get('custom_prompt', ''),
                api_name=kwargs.get('api_name', 'openai'),
                api_key=kwargs.get('api_key'),
                temp=kwargs.get('temperature', 0.7),
                system_message=kwargs.get('system_message', 'Summarize this article concisely.')
            )
            return summary
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return "Summary generation failed"

    async def scrape_sitemap(
        self,
        sitemap_url: str,
        filter_func: Optional[Callable[[str], bool]] = None,
        max_urls: Optional[int] = None,
        custom_cookies: Optional[List[Dict[str, Any]]] = None,
        user_agent: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        task_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape all URLs from a sitemap"""
        # Egress guard for sitemap endpoint
        try:
            from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
            pol = evaluate_url_policy(sitemap_url)
            if not getattr(pol, 'allowed', False):
                logger.error(f"Egress denied for sitemap: {getattr(pol, 'reason', 'blocked')}")
                return []
        except Exception as _e:
            logger.error(f"Egress policy evaluation failed: {_e}")
            return []
        if task_id and task_id not in self._progress:
            self._progress[task_id] = {
                "status": "in_progress",
                "total_urls": 0,
                "processed_urls": 0,
                "current_url": sitemap_url,
                "started_at": datetime.now().isoformat(),
            }
        headers = self._build_request_headers(user_agent, custom_headers)
        cookies = self._build_cookie_map(sitemap_url, custom_cookies)
        resp = await afetch(
            method="GET",
            url=sitemap_url,
            headers=headers,
            cookies=cookies,
        )
        try:
            content = resp.text
        finally:
            await self._close_response(resp)

        # Parse sitemap
        soup = BeautifulSoup(content, 'xml')
        urls = []

        for loc in soup.find_all('loc'):
            url = loc.text.strip()
            if filter_func and not filter_func(url):
                continue
            urls.append(url)
            if max_urls and len(urls) >= max_urls:
                break

        logger.info(f"Found {len(urls)} URLs in sitemap")
        self._set_progress(task_id, total_urls=len(urls))

        # Scrape all URLs
        results = await self.scrape_multiple(
            urls,
            custom_cookies=custom_cookies,
            user_agent=user_agent,
            custom_headers=custom_headers,
        )
        self._set_progress(
            task_id,
            processed_urls=len(results),
            status="completed",
            completed_at=datetime.now().isoformat(),
        )
        return results

    async def recursive_scrape(
        self,
        base_url: str,
        max_pages: int = 100,
        max_depth: int = 3,
        url_filter: Optional[Callable[[str], bool]] = None,
        custom_cookies: Optional[List[Dict[str, Any]]] = None,
        user_agent: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        task_id: Optional[str] = None,
        *,
        include_external_override: Optional[bool] = None,
        score_threshold_override: Optional[float] = None,
        crawl_strategy: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recursively scrape a website"""
        # Egress guard for base URL
        try:
            from tldw_Server_API.app.core.Security.egress import evaluate_url_policy
            pol = evaluate_url_policy(base_url)
            if not getattr(pol, 'allowed', False):
                logger.error(f"Egress denied for recursive scrape: {getattr(pol, 'reason', 'blocked')}")
                return []
        except Exception as _e:
            logger.error(f"Egress policy evaluation failed: {_e}")
            return []
        if task_id and task_id not in self._progress:
            self._progress[task_id] = {
                "status": "in_progress",
                "total_pages": max_pages,
                "pages_scraped": 0,
                "current_url": base_url,
                "started_at": datetime.now().isoformat(),
            }
        visited: Set[str] = set()
        base_norm = normalize_for_crawl(base_url, base_url)
        # Build filter chain based on config (include_external, allow/deny, patterns, content types)
        # Prefer instance config provided at construction; do not override with
        # on-disk config unless necessary. Tests pass config={} to exercise
        # default behavior deterministically.
        wc = self.config if isinstance(self.config, dict) else {}
        include_external_flag = bool(wc.get('web_crawl_include_external', False))
        if include_external_override is not None:
            include_external_flag = bool(include_external_override)
        allowed_raw = wc.get('web_crawl_allowed_domains') or ""
        blocked_raw = wc.get('web_crawl_blocked_domains') or ""
        def _split(s: str) -> Set[str]:
            return {t.strip().lower() for t in str(s).split(',') if t.strip()}
        allowed_set = _split(allowed_raw)
        blocked_set = _split(blocked_raw)
        base_host = urlparse(base_norm).netloc.lower()
        domain_allowed = None if include_external_flag else {base_host}
        if allowed_set:
            domain_allowed = allowed_set if include_external_flag else (allowed_set | {base_host})

        default_excludes = [
            '/tag/', '/category/', '/author/', '/search/', '/page/',
            'wp-content', 'wp-includes', 'wp-json', 'wp-admin',
            'login', 'register', 'cart', 'checkout', 'account',
            '.jpg', '.png', '.gif', '.pdf', '.zip'
        ]

        filter_chain = FilterChain([
            DomainFilter(allowed=domain_allowed, blocked=blocked_set or None),
            ContentTypeFilter(),
            URLPatternFilter(include_patterns=None, exclude_patterns=default_excludes),
        ])

        # Optional robots filter controlled by config (default: respect robots)
        respect_robots_default = wc.get('web_scraper_respect_robots', True)
        if isinstance(respect_robots_default, str):
            respect_robots_default = respect_robots_default.strip().lower() in {"1", "true", "yes", "on", "y"}
        robots_filter: Optional[RobotsFilter] = None
        if bool(respect_robots_default):
            robots_ua = user_agent or DEFAULT_USER_AGENT
            robots_filter = RobotsFilter(robots_ua, ttl_seconds=1800, backend="httpx", timeout=5.0)

        # Build composite scorer
        scorers = [
            PathDepthScorer(optimal_depth=3, weight=1.0),
            CTScorer(weight=1.0),
            FreshnessScorer(weight=1.0),
        ]
        # Optional keyword scorer
        if bool(wc.get('web_crawl_enable_keyword_scorer', False)):
            kw_raw = wc.get('web_crawl_keywords') or ''
            keywords = [t.strip() for t in str(kw_raw).split(',') if t.strip()]
            if keywords:
                scorers.append(KeywordRelevanceScorer(keywords=keywords, weight=1.0))
        # Optional domain authority map
        if bool(wc.get('web_crawl_enable_domain_map', False)):
            dom_raw = wc.get('web_crawl_domain_map') or ''
            dom_map: Dict[str, float] = {}
            if isinstance(dom_raw, dict):
                dom_map = {str(k).lower(): float(v) for k, v in dom_raw.items()}
            else:
                s = str(dom_raw).strip()
                if s.startswith('{'):
                    try:
                        import json as _json
                        obj = _json.loads(s)
                        if isinstance(obj, dict):
                            dom_map = {str(k).lower(): float(v) for k, v in obj.items()}
                    except Exception:
                        dom_map = {}
                else:
                    for part in s.split(','):
                        if ':' in part:
                            d, val = part.split(':', 1)
                            try:
                                dom_map[str(d).strip().lower()] = float(val)
                            except Exception:
                                pass
            if dom_map:
                scorers.append(DomainAuthorityScorer(domain_weights=dom_map, default_weight=0.5, weight=1.0))

        composite = CompositeScorer(scorers, normalize=True)
        order_scorer = PathDepthScorer(optimal_depth=3, weight=1.0)
        try:
            score_threshold = float(wc.get('web_crawl_score_threshold', 0.0))
        except Exception:
            score_threshold = 0.0
        if score_threshold_override is not None:
            try:
                score_threshold = float(score_threshold_override)
            except Exception:
                pass

        results = []

        # Determine effective strategy (default to best_first)
        eff_strategy = (crawl_strategy or str(wc.get('web_crawl_strategy', 'best_first'))).strip().lower()

        if eff_strategy in {"best_first", "best-first", "bestfirst"}:
            # Build best-first priority queue with tie-breaker on path segment count
            pq: List[Tuple[float, int, int, str, Optional[str]]] = []  # (-score, bfs_depth, -path_segments, url, parent)
            seen: Set[str] = set()
            try:
                start_score = order_scorer.score(base_norm)
            except Exception:
                start_score = 0.0
            # Use path segment count for tie-breaks (deeper paths first)
            try:
                from urllib.parse import urlparse as _urlparse
                _ps = len([seg for seg in (_urlparse(base_url).path or '/').split('/') if seg])
            except Exception:
                _ps = 0
            heappush(pq, (-float(start_score), 0, -_ps, base_url, None))
            seen.add(base_norm)
            # Initial metrics
            try:
                log_histogram("webscraping.crawl.score", float(start_score), labels={"stage": "start"})
            except Exception:
                pass
            try:
                log_gauge("webscraping.crawl.queue_size", float(len(pq)))
            except Exception:
                pass

            while pq and len(results) < max_pages:
                # Gauge: current queue size at loop start
                try:
                    log_gauge("webscraping.crawl.queue_size", float(len(pq)))
                except Exception:
                    pass
                # Pop up to batch size items
                remaining = max_pages - len(results)
                batch_n = min(BEST_FIRST_BATCH_SIZE, remaining)
                batch: List[Tuple[float, int, int, str, Optional[str]]] = []
                while pq and len(batch) < batch_n:
                    neg_s, depth, _tie, url, parent = heappop(pq)
                    cur = normalize_for_crawl(url, base_norm)
                    if cur in visited or depth > max_depth:
                        # Count URL skipped due to visited or exceeding depth
                        try:
                            log_counter("webscraping.crawl.urls_skipped", labels={"reason": "visited_or_depth"})
                        except Exception:
                            pass
                        if cur in visited:
                            logger.debug(f"Skip URL (visited): {cur}")
                        elif depth > max_depth:
                            logger.debug(f"Skip URL (depth>{max_depth}): {cur}")
                        continue
                    # Keep original URL string for scraping/results; use 'cur' only for visited checks
                    batch.append((neg_s, depth, _tie, url, parent))
                    visited.add(cur)

                if not batch:
                    continue

                # Gauge: current processing depth (first item in batch)
                try:
                    log_gauge("webscraping.crawl.depth", float(batch[0][1]))
                except Exception:
                    pass

                batch_urls = [u for (_, _, _, u, _) in batch]
                batch_results = await self.scrape_multiple(
                    batch_urls,
                    method="trafilatura",
                    custom_cookies=custom_cookies,
                    user_agent=user_agent,
                    custom_headers=custom_headers,
                )

                # Map url -> (neg_score, depth, parent)
                meta_map = {u: (neg_s, d, p) for (neg_s, d, _tie, u, p) in batch}

                for res in batch_results:
                    r_url = res.get('url') or ''
                    neg_score, depth, parent = meta_map.get(r_url, (0.0, 0, None))
                    # Attach traversal metadata
                    res.setdefault('metadata', {})
                    # Score is derived from queue priority (negated)
                    try:
                        computed_score = float(-neg_score)
                    except Exception:
                        # Fallback compute on demand
                        try:
                            computed_score = float(composite.score(r_url))
                        except Exception:
                            computed_score = 0.0
                    res['metadata'].update({'depth': depth, 'parent_url': parent, 'score': computed_score})

                    if res.get('extraction_successful'):
                        logger.debug(f"Crawled page success: {r_url} depth={depth} score={computed_score:.3f}")
                        try:
                            log_counter("webscraping.crawl.pages_crawled")
                        except Exception:
                            pass
                        results.append(res)
                        # Discovery
                        if depth < max_depth:
                            # remaining capacity for enqueueing new links
                            remaining = max_pages - len(results)
                            if remaining <= 0:
                                break
                            links = await self._extract_links(r_url, res.get('content', ''))
                            try:
                                log_counter("webscraping.crawl.links_discovered", value=len(links))
                            except Exception:
                                pass
                            for link in links:
                                if remaining <= 0:
                                    break
                                cand = normalize_for_crawl(link, r_url)
                                if cand in visited or cand in seen:
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "dup_seen"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (duplicate): {cand}")
                                    continue
                                if not filter_chain.apply(cand):
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "filter_chain"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (filters reject): {cand}")
                                    continue
                                # Enforce path-depth limit relative to site root to align with expectations
                                try:
                                    from urllib.parse import urlparse as _urlparse
                                    _ps_cand = len([seg for seg in (_urlparse(cand).path or '/').split('/') if seg])
                                except Exception:
                                    _ps_cand = 0
                                if _ps_cand > max_depth:
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "path_depth"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (path depth>{max_depth}): {cand}")
                                    continue
                                # Optional robots gating (execute only for egress-allowed hosts)
                                if robots_filter is not None:
                                    try:
                                        allowed = await robots_filter.allowed(cand)
                                    except Exception:
                                        allowed = True  # fail open
                                    if not allowed:
                                        try:
                                            parsed = urlparse(cand)
                                            increment_counter("scrape_blocked_by_robots_total", labels={"domain": parsed.netloc})
                                        except Exception:
                                            pass
                                        try:
                                            log_counter("webscraping.crawl.urls_skipped", labels={"reason": "robots"})
                                        except Exception:
                                            pass
                                        logger.debug(f"Skip URL (robots disallow): {cand}")
                                        continue
                                try:
                                    s_val = composite.score(cand)
                                except Exception:
                                    s_val = 0.0
                                # Histogram: candidate score distribution
                                try:
                                    log_histogram("webscraping.crawl.score", float(s_val))
                                except Exception:
                                    pass
                                if s_val < score_threshold:
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "below_threshold"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (score {s_val:.3f} < threshold {score_threshold:.3f}): {cand}")
                                    continue
                                if url_filter and not url_filter(cand):
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "custom_filter"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (custom filter): {cand}")
                                    continue
                                # Tie-break on path segment count (deeper paths first)
                                try:
                                    from urllib.parse import urlparse as _urlparse
                                    _ps2 = len([seg for seg in (_urlparse(cand).path or '/').split('/') if seg])
                                except Exception:
                                    _ps2 = 0
                                try:
                                    ord_val = float(order_scorer.score(cand))
                                except Exception:
                                    ord_val = float(s_val)
                                heappush(pq, (-float(ord_val), depth + 1, -_ps2, cand, r_url))
                                seen.add(cand)
                                remaining -= 1
                                logger.debug(f"Enqueue URL (score={s_val:.3f}, depth={depth+1}): {cand}")
                                # Gauge: queue size after enqueue
                                try:
                                    log_gauge("webscraping.crawl.queue_size", float(len(pq)))
                                except Exception:
                                    pass
                self._set_progress(
                    task_id,
                    pages_scraped=len(results),
                    total_pages=max_pages,
                    current_url=(batch_urls[-1] if batch_urls else None),
                    queue_size=len(pq),
                    visited=len(visited),
                )
        else:
            # FIFO/BFS strategy
            from collections import deque as _deque
            q: _deque[Tuple[int, str, Optional[str]]] = _deque()
            seen_fifo: Set[str] = set()
            q.append((0, base_url, None))
            seen_fifo.add(base_norm)
            try:
                log_gauge("webscraping.crawl.queue_size", float(len(q)))
            except Exception:
                pass

            while q and len(results) < max_pages:
                remaining = max_pages - len(results)
                batch_n = min(BEST_FIRST_BATCH_SIZE, remaining)
                batch_fifo: List[Tuple[int, str, Optional[str]]] = []
                while q and len(batch_fifo) < batch_n:
                    depth, url, parent = q.popleft()
                    cur = normalize_for_crawl(url, base_norm)
                    if cur in visited or depth > max_depth:
                        try:
                            log_counter("webscraping.crawl.urls_skipped", labels={"reason": "visited_or_depth"})
                        except Exception:
                            pass
                        if cur in visited:
                            logger.debug(f"Skip URL (visited): {cur}")
                        elif depth > max_depth:
                            logger.debug(f"Skip URL (depth>{max_depth}): {cur}")
                        continue
                    # Preserve original 'url' string for scraping/results; use 'cur' only for visited checks
                    batch_fifo.append((depth, url, parent))
                    visited.add(cur)

                if not batch_fifo:
                    continue

                try:
                    log_gauge("webscraping.crawl.depth", float(batch_fifo[0][0]))
                except Exception:
                    pass

                batch_urls = [u for (d, u, p) in batch_fifo]
                batch_results = await self.scrape_multiple(
                    batch_urls,
                    method="trafilatura",
                    custom_cookies=custom_cookies,
                    user_agent=user_agent,
                    custom_headers=custom_headers,
                )

                meta_map_fifo = {u: (d, p) for (d, u, p) in batch_fifo}

                for res in batch_results:
                    r_url = res.get('url') or ''
                    depth, parent = meta_map_fifo.get(r_url, (0, None))
                    res.setdefault('metadata', {})
                    try:
                        computed_score = float(composite.score(r_url))
                        log_histogram("webscraping.crawl.score", computed_score, labels={"stage": "visit"})
                    except Exception:
                        computed_score = 0.0
                    res['metadata'].update({'depth': depth, 'parent_url': parent, 'score': computed_score})

                    if res.get('extraction_successful'):
                        logger.debug(f"Crawled page success: {r_url} depth={depth} score={computed_score:.3f}")
                        try:
                            log_counter("webscraping.crawl.pages_crawled")
                        except Exception:
                            pass
                        results.append(res)

                        if depth < max_depth:
                            remaining_cap = max_pages - len(results)
                            if remaining_cap <= 0:
                                break
                            links = await self._extract_links(r_url, res.get('content', ''))
                            try:
                                log_counter("webscraping.crawl.links_discovered", value=len(links))
                            except Exception:
                                pass
                            for link in links:
                                if remaining_cap <= 0:
                                    break
                                cand = normalize_for_crawl(link, r_url)
                                if cand in visited or cand in seen_fifo:
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "dup_seen"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (duplicate): {cand}")
                                    continue
                                if not filter_chain.apply(cand):
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "filter_chain"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (filters reject): {cand}")
                                    continue
                                if robots_filter is not None:
                                    try:
                                        allowed = await robots_filter.allowed(cand)
                                    except Exception:
                                        allowed = True  # fail open
                                    if not allowed:
                                        try:
                                            parsed = urlparse(cand)
                                            increment_counter("scrape_blocked_by_robots_total", labels={"domain": parsed.netloc})
                                        except Exception:
                                            pass
                                        try:
                                            log_counter("webscraping.crawl.urls_skipped", labels={"reason": "robots"})
                                        except Exception:
                                            pass
                                        logger.debug(f"Skip URL (robots disallow): {cand}")
                                        continue
                                try:
                                    s_val = float(composite.score(cand))
                                    log_histogram("webscraping.crawl.score", s_val, labels={"stage": "discovery"})
                                except Exception:
                                    s_val = 0.0
                                if s_val < score_threshold:
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "below_threshold"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (score {s_val:.3f} < threshold {score_threshold:.3f}): {cand}")
                                    continue
                                if url_filter and not url_filter(cand):
                                    try:
                                        log_counter("webscraping.crawl.urls_skipped", labels={"reason": "custom_filter"})
                                    except Exception:
                                        pass
                                    logger.debug(f"Skip URL (custom filter): {cand}")
                                    continue
                                q.append((depth + 1, cand, r_url))
                                seen_fifo.add(cand)
                                remaining_cap -= 1
                                logger.debug(f"Enqueue URL (FIFO, depth={depth+1}): {cand}")
                                try:
                                    log_gauge("webscraping.crawl.queue_size", float(len(q)))
                                except Exception:
                                    pass
                self._set_progress(
                    task_id,
                    pages_scraped=len(results),
                    total_pages=max_pages,
                    current_url=(batch_urls[-1] if batch_urls else None),
                    queue_size=len(q),
                    visited=len(visited),
                )

        self._set_progress(
            task_id,
            status="completed",
            completed_at=datetime.now().isoformat(),
        )
        return results

    async def _extract_links(self, base_url: str, content: str) -> List[str]:
        """Extract links. If provided content looks like plain text, fetch HTML first."""
        html_text = content or ""
        # Heuristic: if content lacks HTML tags, fetch the page HTML
        if '<a' not in html_text and '<html' not in html_text:
            try:
                headers = self._build_request_headers(None, None)
                cookies = self._build_cookie_map(base_url, None)
                resp = await afetch(
                    method="GET",
                    url=base_url,
                    headers=headers,
                    cookies=cookies,
                )
                try:
                    html_text = resp.text
                finally:
                    await self._close_response(resp)
            except Exception as e:
                logger.warning(f"Failed to fetch HTML for link extraction: {e}")
                return []

        try:
            soup = BeautifulSoup(html_text, 'html.parser')
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if href and not href.startswith('#'):
                    links.append(href)
            return links
        except Exception as e:
            logger.warning(f"Error parsing links from content: {e}")
            return []

    def get_progress(self, task_name: str) -> Dict[str, Any]:
        """Get progress for a specific task"""
        return self._progress.get(task_name, {})

    async def save_progress(self, task_name: str, filepath: Path):
        """Save progress to file for resumability"""
        progress_data = self._progress.get(task_name, {})
        async with aiofiles.open(filepath, 'w') as f:
            await f.write(json.dumps(progress_data, indent=2))

    async def load_progress(self, task_name: str, filepath: Path):
        """Load progress from file"""
        if filepath.exists():
            async with aiofiles.open(filepath, 'r') as f:
                content = await f.read()
                self._progress[task_name] = json.loads(content)


# Integration with existing system
async def create_enhanced_scraper() -> EnhancedWebScraper:
    """Create and initialize enhanced scraper"""
    scraper = EnhancedWebScraper()
    await scraper.start()
    return scraper


# Example usage
if __name__ == "__main__":
    async def test_enhanced_scraper():
        """Test the enhanced scraper"""
        scraper = await create_enhanced_scraper()

        try:
            # Test single article scraping
            print("Testing single article scraping...")
            result = await scraper.scrape_article(
                "https://example.com/article",
                method="trafilatura"
            )
            print(f"Result: {result['title'] if result.get('extraction_successful') else result['error']}")

            # Test multiple URL scraping
            print("\nTesting multiple URL scraping...")
            urls = [
                "https://example.com/article1",
                "https://example.com/article2",
                "https://example.com/article3"
            ]
            results = await scraper.scrape_multiple(
                urls,
                priority=JobPriority.HIGH,
                summarize=True
            )
            print(f"Scraped {len(results)} articles")

            # Test recursive scraping
            print("\nTesting recursive scraping...")
            results = await scraper.recursive_scrape(
                "https://example.com",
                max_pages=10,
                max_depth=2
            )
            print(f"Recursively scraped {len(results)} pages")

            # Get queue status
            status = scraper.job_queue.get_status()
            print(f"\nQueue status: {status}")

        finally:
            await scraper.stop()

    asyncio.run(test_enhanced_scraper())
