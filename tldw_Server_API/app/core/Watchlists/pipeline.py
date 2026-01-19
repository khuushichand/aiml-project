"""
Watchlists fetch→ingest pipeline

Executes a watchlist job for a given user:
- Select sources based on job scope (sources/groups/tags)
- For each source:
  - If `rss`: fetch feed items, then fetch each linked page and ingest
  - If `site`: fetch page and ingest
- Apply job-level filters (include/exclude/flag) before ingestion, short-circuiting on the
  highest-priority matching rule. Filter decisions and tallies are recorded into run stats
  (filters_matched, filters_actions, filter_tallies) and filtered items are recorded into
  `scraped_items` with status="filtered".
- Persist per-run stats for each run, upsert Collections content_items for ingested
  items regardless of Media DB persistence, and append media IDs to scrape_run_items
  only when Media DB persistence is enabled

Include-only gating semantics:
- A job may set `require_include=true` in its filters payload. When any include rules exist and
  this is true, only include-matched candidates are ingested; others are treated as filtered.
- If the job does not set `require_include`, the pipeline checks the organization default
  via organizations.metadata.watchlists.require_include_default (or flat key
  watchlists_require_include_default). If neither is set, it falls back to the environment
  variable `WATCHLISTS_REQUIRE_INCLUDE_DEFAULT`. Include gating only applies when include rules exist.

Notes:
- In tests (TEST_MODE=1), RSS fetch returns a fake item and site fetch may be bypassed.
  We count items but avoid network.
"""

from __future__ import annotations

import asyncio
import os
import json
import inspect
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase, SourceRow
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.Collections.utils import hash_text_sha256, truncate_text, word_count
from tldw_Server_API.app.core.Collections.embedding_queue import enqueue_embeddings_job_for_item
from tldw_Server_API.app.core.Watchlists.fetchers import (
    fetch_rss_feed,
    fetch_rss_feed_history,
    fetch_site_article_async,
    fetch_site_items_with_rules,
)
from tldw_Server_API.app.core.Watchlists.filters import normalize_filters, evaluate_filters
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def _forums_enabled() -> bool:
    return str(os.getenv("WATCHLIST_FORUMS_ENABLED", "")).strip().lower() in {"1", "true", "yes", "on"}


def _forum_delay_seconds() -> float:
    try:
        delay_ms = int(os.getenv("WATCHLIST_FORUMS_DELAY_MS", "1500") or 1500)
    except Exception:
        delay_ms = 1500
    if delay_ms < 0:
        delay_ms = 0
    return delay_ms / 1000.0


def _normalize_tz(tz: Optional[str]) -> str:
    if not tz or tz.upper() == "UTC":
        return "UTC"
    t = tz.strip().upper()
    if t.startswith("UTC+") or t.startswith("UTC-"):
        try:
            sign = 1 if t[3] == "+" else -1
            hours = int(t[4:])
            etc_offset = -sign * hours
            return f"Etc/GMT{('+' if etc_offset>0 else '')}{etc_offset}" if etc_offset != 0 else "Etc/GMT"
        except Exception:
            return "UTC"
    return tz


def fetch_site_article(url: str):
    """Wrapper for article fetch to allow test monkeypatching with sync or async callables."""
    return fetch_site_article_async(url)


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _compute_next_run(cron: Optional[str], timezone_str: Optional[str]) -> Optional[str]:
    if not cron:
        return None
    try:
        from apscheduler.triggers.cron import CronTrigger
        tz = _normalize_tz(timezone_str) or "UTC"
        trigger = CronTrigger.from_crontab(cron, timezone=tz)
        now = datetime.now(trigger.timezone)
        nxt = trigger.get_next_fire_time(None, now)
        return nxt.isoformat() if nxt else None
    except Exception:
        return None


_truncate = truncate_text
_hash_content = hash_text_sha256
_word_count = word_count


def _resolve_collections_origin(
    source_settings: Optional[Dict[str, Any]],
    job_output_prefs: Optional[Dict[str, Any]],
    *,
    default: str = "watchlist",
) -> str:
    for cfg in (source_settings, job_output_prefs):
        if not isinstance(cfg, dict):
            continue
        origin = cfg.get("collections_origin")
        if isinstance(origin, str) and origin.strip():
            return origin.strip()
        nested = cfg.get("collections")
        if isinstance(nested, dict):
            origin = nested.get("origin")
            if isinstance(origin, str) and origin.strip():
                return origin.strip()
    return default


def _maybe_promote_feed_schedule(
    *,
    db: WatchlistsDatabase,
    job,
    job_output_prefs: Dict[str, Any],
) -> None:
    schedule_cfg = job_output_prefs.get("collections_schedule")
    if not isinstance(schedule_cfg, dict):
        return
    if schedule_cfg.get("mode") != "hourly_then_daily":
        return
    if schedule_cfg.get("promoted") is True:
        return
    daily_expr = str(schedule_cfg.get("daily_expr") or "0 0 * * *").strip()
    if not daily_expr:
        return
    try:
        promote_after = int(schedule_cfg.get("promote_after_hours", 24) or 24)
    except Exception:
        promote_after = 24
    if promote_after <= 0:
        promote_after = 24
    created_raw = schedule_cfg.get("created_at") or getattr(job, "created_at", None)
    if not created_raw:
        return
    try:
        created_dt = datetime.fromisoformat(str(created_raw))
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    if now_utc < created_dt + timedelta(hours=promote_after):
        return

    schedule_cfg["promoted"] = True
    schedule_cfg["promoted_at"] = _utcnow_iso()
    job_output_prefs["collections_schedule"] = schedule_cfg
    patch = {"output_prefs_json": json.dumps(job_output_prefs)}
    if str(job.schedule_expr or "").strip() != daily_expr:
        patch["schedule_expr"] = daily_expr
    try:
        updated = db.update_job(int(job.id), patch)
    except Exception as exc:
        logger.debug(f"collections schedule promote failed for job {getattr(job, 'id', '?')}: {exc}")
        return
    try:
        next_run = _compute_next_run(updated.schedule_expr, updated.schedule_timezone)
        db.set_job_history(job_id=int(updated.id), next_run_at=next_run)
    except Exception:
        pass
    try:
        if updated.wf_schedule_id:
            from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
            svc = get_workflows_scheduler()
            svc.update(
                updated.wf_schedule_id,
                {
                    "cron": updated.schedule_expr or "* * * * *",
                    "timezone": _normalize_tz(updated.schedule_timezone) or "UTC",
                    "enabled": bool(updated.active),
                },
            )
    except Exception as exc:
        logger.debug(f"collections schedule promote sync failed for job {getattr(job, 'id', '?')}: {exc}")


def _select_sources_for_scope(db: WatchlistsDatabase, scope: Dict[str, Any]) -> List[SourceRow]:
    """Resolve sources given a job scope.

    Scope semantics (minimal):
    - sources: explicit source IDs (ints)
    - tags: list of tag names (AND semantics)
    - groups: list of group IDs (OR semantics across groups)
    """
    selected: Dict[int, SourceRow] = {}
    # Explicit IDs
    for sid in map(int, scope.get("sources", []) or []):
        try:
            r = db.get_source(sid)
            if int(r.active or 0) == 1:
                selected[int(r.id)] = r
        except Exception:
            continue
    # Tags
    tag_names = scope.get("tags") or []
    if tag_names:
        rows, _ = db.list_sources(q=None, tag_names=tag_names, limit=10000, offset=0)
        for r in rows:
            if int(r.active or 0) == 1:
                selected[int(r.id)] = r
    # Groups
    group_ids = scope.get("groups") or []
    if group_ids:
        try:
            rows = db.list_sources_by_group_ids(group_ids)
            for r in rows:
                if int(r.active or 0) == 1:
                    selected[int(r.id)] = r
        except Exception:
            pass
    return list(selected.values())


async def run_watchlist_job(user_id: int, job_id: int) -> Dict[str, Any]:
    """Run the watchlist fetch→ingest pipeline for this user/job.

    Returns minimal stats: { run_id, items_found, items_ingested }.
    """
    db = WatchlistsDatabase.for_user(user_id)
    collections_db = CollectionsDatabase.for_user(user_id)
    job = db.get_job(job_id)
    is_first_run = True if not getattr(job, "last_run_at", None) else False
    run = db.create_run(job_id=job_id, status="running")

    job_output_prefs: Dict[str, Any] = {}
    try:
        if getattr(job, "output_prefs_json", None):
            job_output_prefs = json.loads(job.output_prefs_json or "{}")
            if not isinstance(job_output_prefs, dict):
                job_output_prefs = {}
    except Exception as e:
        logger.exception(
            "Failed to parse job.output_prefs_json; job_id={} job_record_id={} job_repr={} "
            "output_prefs_json={!r} error={}",
            job_id,
            getattr(job, "id", None),
            repr(job),
            getattr(job, "output_prefs_json", None),
            e,
        )
        job_output_prefs = {}
    ingest_cfg = job_output_prefs.get("ingest") if isinstance(job_output_prefs, dict) else None
    persist_to_media_db = False
    if isinstance(ingest_cfg, dict) and "persist_to_media_db" in ingest_cfg:
        persist_to_media_db = bool(ingest_cfg.get("persist_to_media_db"))
    elif isinstance(job_output_prefs, dict) and isinstance(job_output_prefs.get("persist_to_media_db"), bool):
        persist_to_media_db = bool(job_output_prefs.get("persist_to_media_db"))

    # Resolve per-user media DB path and instantiate when requested
    mdb = None
    if persist_to_media_db:
        media_db_path = str(DatabasePaths.get_media_db_path(int(user_id)))
        mdb = create_media_database(client_id=str(user_id), db_path=media_db_path)

    # Fetch scope and sources
    scope = {}
    try:
        scope = json.loads(job.scope_json or "{}") if job.scope_json else {}
    except Exception:
        scope = {}
    sources = _select_sources_for_scope(db, scope or {})

    items_found = 0
    items_ingested = 0
    # Allow tags on source to flow into ingestion keywords
    def _keywords_for_source(sr: SourceRow) -> List[str]:
        try:
            return [t for t in (sr.tags or []) if t]
        except Exception:
            return []

    # TEST_MODE short-circuit for offline tests: do not perform network
    test_mode = os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")

    # Load job-level filters + gating toggle (bridge from SUBS Import Rules)
    job_filters: List[Dict[str, Any]] = []
    job_require_include: Optional[bool] = None
    try:
        if getattr(job, "job_filters_json", None):
            raw = json.loads(job.job_filters_json or "{}")
            job_filters = normalize_filters(raw)
            if isinstance(raw, dict) and "require_include" in raw:
                try:
                    job_require_include = bool(raw.get("require_include"))
                except Exception:
                    job_require_include = None
    except Exception:
        job_filters = []
        job_require_include = None

    async def _org_require_include_default() -> bool:
        # Read from active org metadata when available; fallback to env var
        try:
            scope = get_scope()
            org_id = getattr(scope, "effective_org_id", None) if scope else None
            if org_id is not None:
                pool = await get_db_pool()
                row = await pool.fetchone("SELECT metadata FROM organizations WHERE id = ?", int(org_id))
                if row is not None:
                    meta = row.get("metadata")
                    try:
                        import json as _json
                        if isinstance(meta, str):
                            meta_dict = _json.loads(meta)
                        elif isinstance(meta, (dict,)):
                            meta_dict = meta
                        else:
                            meta_dict = None
                        if isinstance(meta_dict, dict):
                            # Accept either nested or flat key
                            if isinstance(meta_dict.get("watchlists"), dict):
                                val = meta_dict.get("watchlists", {}).get("require_include_default")
                                if isinstance(val, bool):
                                    return val
                            flat = meta_dict.get("watchlists_require_include_default")
                            if isinstance(flat, bool):
                                return flat
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            return str(os.getenv("WATCHLISTS_REQUIRE_INCLUDE_DEFAULT", "")).strip().lower() in {"1", "true", "yes", "on"}
        except Exception:
            return False

    include_rules_exist = any((str(f.get("action")) == "include") for f in job_filters)
    org_default = await _org_require_include_default()
    effective_require_include = job_require_include if (job_require_include is not None) else org_default
    include_gating_active = bool(effective_require_include and include_rules_exist)

    # Filter evaluation statistics
    filter_stats: Dict[str, Any] = {
        "filters_matched": 0,
        "filters_actions": {"include": 0, "exclude": 0, "flag": 0},
        "filter_tallies": {},
    }

    # Bounded debug logging for filter decisions
    try:
        _max_debug = int(os.getenv("WATCHLISTS_FILTER_DEBUG_MAX", "100") or 100)
    except Exception:
        _max_debug = 100
    _debug_count = 0

    # History/backfill counters for the run
    history_pages_total = 0
    history_any_stop = False
    history_used = False

    for src in sources:
            try:
                src_type = (src.source_type or "").lower()
                if src_type == "forum":
                    if not _forums_enabled():
                        try:
                            db.update_source_scrape_meta(int(src.id), last_scraped_at=_utcnow_iso(), status="forum_disabled")
                        except Exception:
                            pass
                        continue
                    if not test_mode:
                        await asyncio.sleep(_forum_delay_seconds())
                # Defer source if Retry-After previously set and not elapsed
                if getattr(src, "defer_until", None):
                    try:
                        from datetime import datetime as _dt
                        now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
                        defer_dt = _dt.fromisoformat(str(src.defer_until))
                        if now_utc < defer_dt:
                            # still deferred
                            continue
                        # past due: clear defer
                        try:
                            db.clear_source_defer_until(int(src.id))
                        except Exception:
                            pass
                    except Exception:
                        # if parse fails, continue normal flow
                        pass

                def _record_scraped(
                    *,
                    status: str,
                    url: Optional[str],
                    title: Optional[str],
                    summary: Optional[str],
                    media_id: Optional[int],
                    media_uuid: Optional[str],
                    published_at: Optional[str] = None,
                ) -> None:
                    try:
                        db.record_scraped_item(
                            run_id=run.id,
                            job_id=job_id,
                            source_id=int(src.id),
                            media_id=media_id,
                            media_uuid=media_uuid,
                            url=url,
                            title=title,
                            summary=_truncate(summary),
                            published_at=published_at,
                            tags=_keywords_for_source(src),
                            status=status,
                        )
                    except Exception as rec_err:
                        logger.debug(f"record_scraped_item failed (source_id={getattr(src, 'id', '?')}): {rec_err}")

                if src_type == "rss":
                    urls = [src.url]
                    rss_items: List[Dict[str, Any]]
                    # Per-source settings
                    settings = {}
                    try:
                        settings = json.loads(src.settings_json or "{}") if getattr(src, "settings_json", None) else {}
                    except Exception:
                        settings = {}
                    collections_origin = _resolve_collections_origin(settings, job_output_prefs)
                    rss_limit = int(settings.get("limit", 50)) if isinstance(settings.get("limit", 50), int) else 50
                    # Effective history/backfill options: merge job output_prefs.history over source.settings.history
                    history_cfg = settings.get("history") if isinstance(settings.get("history"), dict) else {}
                    job_hist = (
                        job_output_prefs.get("history")
                        if isinstance(job_output_prefs, dict) and isinstance(job_output_prefs.get("history"), dict)
                        else {}
                    )
                    if job_hist:
                        # shallow-merge, job overrides source
                        merged = dict(history_cfg)
                        merged.update(job_hist)
                        history_cfg = merged
                    hist_strategy = str(history_cfg.get("strategy", "auto")).lower() if isinstance(history_cfg, dict) else "auto"
                    try:
                        hist_max_pages = int(history_cfg.get("max_pages", 1)) if isinstance(history_cfg, dict) else 1
                    except Exception:
                        hist_max_pages = 1
                    if hist_max_pages < 1:
                        hist_max_pages = 1
                    hist_on_304 = bool(history_cfg.get("on_304", False)) if isinstance(history_cfg, dict) else False
                    try:
                        hist_per_page = int(history_cfg.get("per_page_limit")) if isinstance(history_cfg.get("per_page_limit"), int) else None
                    except Exception:
                        hist_per_page = None
                    hist_stop_on_seen = bool(history_cfg.get("stop_on_seen", False)) if isinstance(history_cfg, dict) else False
                    # Load DB seen keys for boundary stop mode
                    seen_keys: List[str] = []
                    if hist_stop_on_seen:
                        try:
                            limit_base = rss_limit if rss_limit > 0 else 50
                            if isinstance(hist_per_page, int) and hist_per_page > 0:
                                limit_base = max(limit_base, hist_per_page)
                            limit = limit_base * max(hist_max_pages, 1)
                            seen_keys = db.list_seen_item_keys(int(src.id), limit=limit)
                        except Exception:
                            seen_keys = []
                    if test_mode:
                        res = {"status": 200, "items": [{"title": "Test Item", "url": "https://example.com/x", "summary": "Test"}]}
                    else:
                        # Use history-aware fetcher when configured
                        use_history = hist_max_pages > 1 or hist_strategy in {"auto", "atom", "wordpress"}
                        if use_history:
                            res = await fetch_rss_feed_history(
                                src.url,
                                etag=getattr(src, "etag", None),
                                last_modified=getattr(src, "last_modified", None),
                                timeout=8.0,
                                tenant_id="default",
                                strategy=hist_strategy,
                                max_pages=hist_max_pages,
                                per_page_limit=hist_per_page,
                                on_304=hist_on_304,
                                stop_on_seen=hist_stop_on_seen,
                                seen_keys=seen_keys,
                            )
                        else:
                            res = await fetch_rss_feed(
                                src.url,
                                etag=getattr(src, "etag", None),
                                last_modified=getattr(src, "last_modified", None),
                                timeout=8.0,
                                tenant_id="default",
                            )
                    status = int(res.get("status", 0) or 0)
                    if status == 304:
                        # nothing new
                        # Increment consecutive not-modified count and optionally apply adaptive backoff
                        try:
                            curr = int(getattr(src, "consec_not_modified", 0) or 0)
                        except Exception:
                            curr = 0
                        new_count = curr + 1
                        # Adaptive backoff parameters
                        import os as _os
                        try:
                            threshold = int(_os.getenv("WATCHLISTS_304_BACKOFF_THRESHOLD", "3") or 3)
                        except Exception:
                            threshold = 3
                        try:
                            base_sec = int(_os.getenv("WATCHLISTS_304_BACKOFF_BASE_SEC", "3600") or 3600)
                        except Exception:
                            base_sec = 3600
                        try:
                            max_sec = int(_os.getenv("WATCHLISTS_304_BACKOFF_MAX_SEC", "21600") or 21600)
                        except Exception:
                            max_sec = 21600
                        try:
                            jitter_pct = float(_os.getenv("WATCHLISTS_304_BACKOFF_JITTER_PCT", "0.1") or 0.1)
                        except Exception:
                            jitter_pct = 0.1

                        defer_until_val = None
                        if new_count >= threshold:
                            exp = new_count - threshold
                            raw = base_sec * (2 ** exp)
                            secs = min(raw, max_sec)
                            # apply ± jitter
                            import random as _rnd
                            j = int(secs * jitter_pct)
                            if j > 0:
                                secs = max(0, secs + _rnd.randint(-j, j))
                            from datetime import timedelta as _td
                            defer_until_val = (datetime.utcnow().replace(tzinfo=timezone.utc) + _td(seconds=secs)).isoformat()
                        try:
                            db.update_source_scrape_meta(
                                int(src.id),
                                last_scraped_at=_utcnow_iso(),
                                status=("not_modified" if defer_until_val is None else f"not_modified_backoff:{secs}"),
                                defer_until=defer_until_val,
                                consec_not_modified=new_count,
                            )
                        except Exception:
                            pass
                        continue
                    if status == 429:
                        # Defer per Retry-After
                        ra = res.get("retry_after")
                        if isinstance(ra, int) and ra > 0:
                            from datetime import timedelta
                            until = (datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(seconds=ra)).isoformat()
                            try:
                                db.update_source_scrape_meta(int(src.id), status="deferred", defer_until=until)
                            except Exception:
                                pass
                        continue
                    if status // 100 != 2:
                        # error path
                        try:
                            db.update_source_scrape_meta(int(src.id), last_scraped_at=_utcnow_iso(), status=f"error:{status}")
                        except Exception:
                            pass
                        continue

                    # 200 OK
                    if res.get("etag") is not None or res.get("last_modified") is not None:
                        try:
                            db.update_source_scrape_meta(int(src.id), etag=res.get("etag"), last_modified=res.get("last_modified"), consec_not_modified=0)
                        except Exception:
                            pass
                    # Accumulate history counters for run stats when applicable
                    try:
                        if isinstance(res.get("pages_fetched"), int):
                            history_pages_total += int(res.get("pages_fetched"))
                            history_used = True
                        if bool(res.get("stop_on_seen_triggered")):
                            history_any_stop = True
                    except Exception:
                        pass
                    rss_items = list(res.get("items") or [])
                    if isinstance(rss_limit, int) and rss_limit > 0:
                        rss_items = rss_items[:rss_limit]
                    items_found += len(rss_items)
                    for it in rss_items:
                        link = it.get("url") or it.get("link")
                        if not link:
                            continue
                        # Item-level dedup check
                        item_key = (it.get("guid") or link or (it.get("title") or ""))
                        # Skip dedup on the very first run (TEST_MODE only) to stabilize offline tests
                        skip_dedup = test_mode and is_first_run
                        if not skip_dedup:
                            try:
                                if db.has_seen_item(int(src.id), item_key):
                                    # Already seen; skip ingestion but count as found
                                    _record_scraped(
                                        status="duplicate",
                                        url=link,
                                        title=it.get("title"),
                                        summary=it.get("summary"),
                                        media_id=None,
                                        media_uuid=None,
                                        published_at=it.get("published"),
                                    )
                                    continue
                            except Exception:
                                pass

                        # Evaluate filters before fetching article
                        decision = None
                        flagged = False
                        try:
                            candidate = {
                                "title": it.get("title"),
                                "summary": it.get("summary"),
                                "content": None,
                                "author": it.get("author"),
                                "published_at": it.get("published"),
                            }
                            decision, meta = evaluate_filters(job_filters, candidate)
                            if _debug_count < _max_debug:
                                logger.debug(
                                    f"watchlists.filter:rss source={getattr(src,'id',None)} decision={decision} gating={include_gating_active} title={(it.get('title') or '')[:60]}"
                                )
                                _debug_count += 1
                            if decision is not None:
                                filter_stats["filters_matched"] += 1
                                if decision in filter_stats["filters_actions"]:
                                    filter_stats["filters_actions"][decision] += 1
                                key = meta.get("key") if isinstance(meta, dict) else None
                                if key:
                                    filter_stats["filter_tallies"][key] = filter_stats["filter_tallies"].get(key, 0) + 1
                            if decision == "exclude":
                                _record_scraped(
                                    status="filtered",
                                    url=link,
                                    title=it.get("title"),
                                    summary=it.get("summary"),
                                    media_id=None,
                                    media_uuid=None,
                                    published_at=it.get("published"),
                                )
                                continue
                            # Include-only gating: if active and no include matched, filter out
                            if include_gating_active and decision != "include":
                                _record_scraped(
                                    status="filtered",
                                    url=link,
                                    title=it.get("title"),
                                    summary=it.get("summary"),
                                    media_id=None,
                                    media_uuid=None,
                                    published_at=it.get("published"),
                                )
                                continue
                            flagged = (decision == "flag")
                        except Exception:
                            flagged = False

                        # Optional: if feed provides full text, skip article fetch
                        rss_cfg = settings.get("rss") if isinstance(settings.get("rss"), dict) else {}
                        prefer_feed = bool(rss_cfg.get("use_feed_content_if_available", False)) if isinstance(rss_cfg, dict) else False
                        try:
                            min_chars = int(rss_cfg.get("feed_content_min_chars", 400)) if isinstance(rss_cfg, dict) else 400
                        except Exception:
                            min_chars = 400
                        article = None
                        if prefer_feed:
                            feed_text = (it.get("summary") or "").strip()
                            if feed_text and len(feed_text) >= max(0, min_chars):
                                article = {
                                    "title": it.get("title") or "Untitled",
                                    "url": link,
                                    "content": feed_text,
                                    "author": it.get("author"),
                                }
                        if article is None:
                            article = None if test_mode else await _maybe_await(fetch_site_article(link))
                        if article is None and test_mode:
                            # In tests, fall back to summary as content
                            article = {
                                "title": it.get("title") or "Untitled",
                                "url": link,
                                "content": it.get("summary") or "",
                                "author": None,
                            }
                        if not article:
                            continue
                        ingested_media_id: Optional[int] = None
                        ingested_media_uuid: Optional[str] = None
                        summary_text = article.get("content") or it.get("summary") or ""
                        if persist_to_media_db and mdb is not None:
                            try:
                                media_id, media_uuid, _msg = mdb.add_media_with_keywords(
                                    url=article.get("url") or link,
                                    title=article.get("title") or (it.get("title") or "Untitled"),
                                    media_type="article",
                                    content=article.get("content") or (it.get("summary") or ""),
                                    author=article.get("author"),
                                    keywords=(_keywords_for_source(src) + (["flagged"] if flagged else [])),
                                    overwrite=False,
                                )
                                if media_id:
                                    ingested_media_id = int(media_id)
                                    ingested_media_uuid = media_uuid
                                    db.append_run_item(run.id, ingested_media_id, source_id=int(src.id))
                            except Exception as e:
                                logger.debug(f"Media DB ingestion failed for {link}: {e}")

                        content_text = article.get("content") or summary_text or ""
                        tags_for_item = _keywords_for_source(src)
                        if flagged and "flagged" not in tags_for_item:
                            tags_for_item = tags_for_item + ["flagged"]
                        metadata_payload = {
                            "source_id": int(src.id),
                            "source_name": getattr(src, "name", None),
                            "job_id": job_id,
                            "run_id": run.id,
                            "media_uuid": ingested_media_uuid,
                            "tags": tags_for_item,
                            "origin": collections_origin,
                        }
                        item_row = None
                        try:
                            item_row = collections_db.upsert_content_item(
                                origin=collections_origin,
                                origin_type=str(src.source_type or ""),
                                origin_id=int(src.id),
                                url=article.get("url") or link,
                                canonical_url=article.get("url") or link,
                                domain=None,
                                title=article.get("title") or (it.get("title") or "Untitled"),
                                summary=_truncate(summary_text, 600),
                                content_hash=_hash_content(content_text),
                                word_count=_word_count(content_text),
                                published_at=it.get("published"),
                                status="new",
                                favorite=False,
                                metadata=metadata_payload,
                                media_id=ingested_media_id,
                                job_id=job_id,
                                run_id=run.id,
                                source_id=int(src.id),
                                read_at=None,
                                tags=tags_for_item,
                            )
                        except Exception as exc:
                            logger.debug(f"Collections upsert failed (rss) for {link}: {exc}")
                        if item_row:
                            items_ingested += 1
                            if item_row.is_new or item_row.content_changed:
                                try:
                                    await enqueue_embeddings_job_for_item(
                                        user_id=user_id,
                                        item_id=item_row.id,
                                        content=content_text,
                                        metadata={
                                            "origin": collections_origin,
                                            "job_id": job_id,
                                            "run_id": run.id,
                                            "tags": tags_for_item,
                                        },
                                    )
                                except Exception as exc:
                                    logger.debug(f"Embedding enqueue failed for watchlist item {item_row.id}: {exc}")
                            try:
                                db.mark_seen_item(
                                    int(src.id),
                                    item_key,
                                    etag=None,
                                    last_modified=(it.get("published") or None),
                                )
                            except Exception as exc:
                                logger.debug(
                                    f"watchlists: failed to mark seen item for source {src.id}: {exc}"
                                )
                            _record_scraped(
                                status="ingested",
                                url=article.get("url") or link,
                                title=article.get("title") or (it.get("title") or "Untitled"),
                                summary=summary_text,
                                media_id=ingested_media_id,
                                media_uuid=ingested_media_uuid,
                                published_at=it.get("published"),
                            )
                        else:
                            _record_scraped(
                                status="error",
                                url=article.get("url") or link,
                                title=article.get("title") or (it.get("title") or "Untitled"),
                                summary=summary_text,
                                media_id=ingested_media_id,
                                media_uuid=ingested_media_uuid,
                                published_at=it.get("published"),
                            )
                            continue

                    # Update last_scraped_at/status for source
                        try:
                            db.update_source_scrape_meta(int(src.id), last_scraped_at=_utcnow_iso(), status="ok")
                        except Exception:
                            pass

                elif src_type in {"site", "forum"}:
                    # Determine discovery preferences
                    settings = {}
                    try:
                        settings = json.loads(src.settings_json or "{}") if getattr(src, "settings_json", None) else {}
                    except Exception:
                        settings = {}
                    collections_origin = _resolve_collections_origin(settings, job_output_prefs)

                    scrape_rules = settings.get("scrape_rules") if isinstance(settings.get("scrape_rules"), dict) else None
                    prefetched_by_url: Dict[str, Dict[str, Any]] = {}
                    urls_to_fetch: List[str] = []

                    if scrape_rules:
                        try:
                            scraped_items = await fetch_site_items_with_rules(
                                base_url=str(scrape_rules.get("list_url") or src.url),
                                rules=scrape_rules,
                                tenant_id="default",
                            )
                        except Exception as exc:
                            logger.debug(f"Scrape rules fetch failed for source {getattr(src, 'id', '?')}: {exc}")
                            scraped_items = []
                        for entry in scraped_items:
                            link = (entry.get("url") or "").strip()
                            if not link:
                                continue
                            if link not in prefetched_by_url:
                                prefetched_by_url[link] = entry
                                urls_to_fetch.append(link)
                        if "top_n" in settings:
                            try:
                                top_limit = max(0, int(settings.get("top_n", 0)))
                            except Exception:
                                top_limit = None
                            if top_limit == 0:
                                urls_to_fetch = []
                            elif top_limit is not None and top_limit < len(urls_to_fetch):
                                urls_to_fetch = urls_to_fetch[:top_limit]
                        if urls_to_fetch:
                            prefetched_by_url = {url: prefetched_by_url[url] for url in urls_to_fetch}
                        if not urls_to_fetch:
                            urls_to_fetch = [src.url]
                    else:
                        top_n = 1
                        try:
                            top_n = int(settings.get("top_n", 1))
                        except Exception:
                            top_n = 1
                        if top_n <= 0:
                            top_n = 1
                        discover_method = str(settings.get("discover_method", "auto")).lower()
                        if top_n > 1:
                            try:
                                from tldw_Server_API.app.core.Watchlists.fetchers import fetch_site_top_links

                                urls_to_fetch = await fetch_site_top_links(src.url, top_n=top_n, method=discover_method)
                            except Exception:
                                urls_to_fetch = [src.url]
                        else:
                            urls_to_fetch = [src.url]

                    if not urls_to_fetch:
                        continue

                    skip_article_fetch = bool(scrape_rules.get("skip_article_fetch")) if isinstance(scrape_rules, dict) else False

                    items_found += len(urls_to_fetch)
                    for page_url in urls_to_fetch:
                        prefetch = prefetched_by_url.get(page_url)
                        item_key = (prefetch.get("guid") if prefetch and prefetch.get("guid") else page_url)
                        skip_dedup = test_mode and is_first_run
                        if not skip_dedup:
                            try:
                                if db.has_seen_item(int(src.id), item_key):
                                    _record_scraped(
                                        status="duplicate",
                                        url=page_url,
                                        title=(prefetch.get("title") if prefetch and prefetch.get("title") else src.name),
                                        summary=(prefetch.get("summary") if prefetch else None),
                                        media_id=None,
                                        media_uuid=None,
                                        published_at=(prefetch.get("published") or prefetch.get("published_raw")) if prefetch else None,
                                    )
                                    continue
                            except Exception:
                                pass

                        article: Optional[Dict[str, Any]] = None
                        if skip_article_fetch and prefetch:
                            article = {
                                "title": prefetch.get("title") or src.name or "Untitled",
                                "url": page_url,
                                "content": prefetch.get("content") or prefetch.get("summary") or "",
                                "author": prefetch.get("author"),
                            }
                        if article is None:
                            if test_mode:
                                article = {"title": src.name or "Untitled", "url": page_url, "content": "", "author": None}
                            else:
                                article = await _maybe_await(fetch_site_article(page_url))
                        if (not article or not article.get("content")) and prefetch:
                            article = article or {}
                            article["title"] = article.get("title") or prefetch.get("title") or src.name
                            article["url"] = article.get("url") or page_url
                            article["content"] = article.get("content") or prefetch.get("content") or prefetch.get("summary") or ""
                            if prefetch.get("author") and not article.get("author"):
                                article["author"] = prefetch.get("author")
                        if not article:
                            _record_scraped(
                                status="error",
                                url=page_url,
                                title=prefetch.get("title") if prefetch and prefetch.get("title") else src.name,
                                summary=prefetch.get("summary") if prefetch else None,
                                media_id=None,
                                media_uuid=None,
                                published_at=prefetch.get("published") if prefetch else None,
                            )
                            continue

                        article["url"] = article.get("url") or page_url
                        if not article.get("title"):
                            article["title"] = prefetch.get("title") if prefetch and prefetch.get("title") else src.name

                        ingested_media_id: Optional[int] = None
                        ingested_media_uuid: Optional[str] = None
                        summary_text = article.get("content") or ""
                        if not summary_text and prefetch:
                            summary_text = prefetch.get("content") or prefetch.get("summary") or ""
                        # Evaluate filters combining article + prefetch metadata
                        decision = None
                        flagged = False
                        try:
                            candidate = {
                                "title": article.get("title") or (prefetch.get("title") if prefetch else None) or src.name,
                                "summary": (prefetch.get("summary") if prefetch else None),
                                "content": article.get("content"),
                                "author": article.get("author") or (prefetch.get("author") if prefetch else None),
                                "published_at": (prefetch.get("published") if prefetch else None),
                            }
                            decision, meta = evaluate_filters(job_filters, candidate)
                            if _debug_count < _max_debug:
                                logger.debug(
                                    f"watchlists.filter:site source={getattr(src,'id',None)} decision={decision} gating={include_gating_active} url={(page_url or '')[:120]}"
                                )
                                _debug_count += 1
                            if decision is not None:
                                filter_stats["filters_matched"] += 1
                                if decision in filter_stats["filters_actions"]:
                                    filter_stats["filters_actions"][decision] += 1
                                key = meta.get("key") if isinstance(meta, dict) else None
                                if key:
                                    filter_stats["filter_tallies"][key] = filter_stats["filter_tallies"].get(key, 0) + 1
                            if decision == "exclude":
                                _record_scraped(
                                    status="filtered",
                                    url=article.get("url") or page_url,
                                    title=article.get("title") or src.name,
                                    summary=(prefetch.get("summary") if prefetch else None),
                                    media_id=None,
                                    media_uuid=None,
                                    published_at=(prefetch.get("published") if prefetch else None),
                                )
                                continue
                            # Include-only gating
                            if include_gating_active and decision != "include":
                                _record_scraped(
                                    status="filtered",
                                    url=article.get("url") or page_url,
                                    title=article.get("title") or src.name,
                                    summary=(prefetch.get("summary") if prefetch else None),
                                    media_id=None,
                                    media_uuid=None,
                                    published_at=(prefetch.get("published") if prefetch else None),
                                )
                                continue
                            flagged = (decision == "flag")
                        except Exception:
                            flagged = False
                        if persist_to_media_db and mdb is not None:
                            try:
                                media_id, media_uuid, _msg = mdb.add_media_with_keywords(
                                    url=article.get("url") or page_url,
                                    title=article.get("title") or src.name,
                                    media_type="article",
                                    content=article.get("content") or summary_text or "",
                                    author=article.get("author"),
                                    keywords=(_keywords_for_source(src) + (["flagged"] if flagged else [])),
                                    overwrite=False,
                                )
                                if media_id:
                                    ingested_media_id = int(media_id)
                                    ingested_media_uuid = media_uuid
                                    db.append_run_item(run.id, ingested_media_id, source_id=int(src.id))
                            except Exception as e:
                                logger.debug(f"Media DB ingestion failed for site {page_url}: {e}")

                        content_text = article.get("content") or summary_text or ""
                        tags_for_item = _keywords_for_source(src)
                        if flagged and "flagged" not in tags_for_item:
                            tags_for_item = tags_for_item + ["flagged"]
                        metadata_payload = {
                            "source_id": int(src.id),
                            "source_name": getattr(src, "name", None),
                            "job_id": job_id,
                            "run_id": run.id,
                            "media_uuid": ingested_media_uuid,
                            "tags": tags_for_item,
                            "origin": collections_origin,
                        }
                        if prefetch and (prefetch.get("published") or prefetch.get("published_raw")):
                            metadata_payload["prefetch_published"] = prefetch.get("published") or prefetch.get("published_raw")
                        item_row = None
                        try:
                            item_row = collections_db.upsert_content_item(
                                origin=collections_origin,
                                origin_type=str(src.source_type or ""),
                                origin_id=int(src.id),
                                url=article.get("url") or page_url,
                                canonical_url=article.get("url") or page_url,
                                domain=None,
                                title=article.get("title") or src.name,
                                summary=_truncate(summary_text, 600),
                                content_hash=_hash_content(content_text),
                                word_count=_word_count(content_text),
                                published_at=(prefetch.get("published") if prefetch else None),
                                status="new",
                                favorite=False,
                                metadata=metadata_payload,
                                media_id=ingested_media_id,
                                job_id=job_id,
                                run_id=run.id,
                                source_id=int(src.id),
                                read_at=None,
                                tags=tags_for_item,
                            )
                        except Exception as exc:
                            logger.debug(f"Collections upsert failed (site) for {page_url}: {exc}")
                        if item_row:
                            items_ingested += 1
                            if item_row.is_new or item_row.content_changed:
                                try:
                                    await enqueue_embeddings_job_for_item(
                                        user_id=user_id,
                                        item_id=item_row.id,
                                        content=content_text,
                                        metadata={
                                            "origin": collections_origin,
                                            "job_id": job_id,
                                            "run_id": run.id,
                                            "tags": tags_for_item,
                                        },
                                    )
                                except Exception as exc:
                                    logger.debug(f"Embedding enqueue failed for watchlist item {item_row.id}: {exc}")
                            try:
                                db.mark_seen_item(
                                    int(src.id),
                                    item_key,
                                    etag=None,
                                    last_modified=(prefetch.get("published") or prefetch.get("published_raw")) if prefetch else None,
                                )
                            except Exception:
                                pass
                            _record_scraped(
                                status="ingested",
                                url=article.get("url") or page_url,
                                title=article.get("title") or src.name,
                                summary=summary_text or (prefetch.get("summary") if prefetch else None),
                                media_id=ingested_media_id,
                                media_uuid=ingested_media_uuid,
                                published_at=(prefetch.get("published") or prefetch.get("published_raw")) if prefetch else None,
                            )
                        else:
                            _record_scraped(
                                status="error",
                                url=article.get("url") or page_url,
                                title=article.get("title") or src.name,
                                summary=summary_text or (prefetch.get("summary") if prefetch else None),
                                media_id=ingested_media_id,
                                media_uuid=ingested_media_uuid,
                                published_at=(prefetch.get("published") or prefetch.get("published_raw")) if prefetch else None,
                            )
                    try:
                        db.update_source_scrape_meta(int(src.id), last_scraped_at=_utcnow_iso(), status="ok")
                    except Exception:
                        pass
                else:
                    # Unknown type - skip
                    continue
            except Exception as e:
                logger.debug(f"Source processing failed (id={getattr(src, 'id', '?')}): {e}")
                try:
                    db.update_source_scrape_meta(int(src.id), last_scraped_at=_utcnow_iso(), status="error")
                except Exception:
                    pass

    stats = {"items_found": items_found, "items_ingested": items_ingested}
    try:
        if filter_stats["filters_matched"]:
            stats["filters_matched"] = int(filter_stats["filters_matched"])  # type: ignore[assignment]
            stats["filters_actions"] = filter_stats["filters_actions"]
            stats["filter_tallies"] = filter_stats["filter_tallies"]
    except Exception:
        pass
    # Attach history/backfill counters when used
    try:
        if history_used:
            stats["history"] = {
                "pages_fetched": int(history_pages_total),
                "stop_on_seen_triggered": bool(history_any_stop),
            }
    except Exception:
        pass
    db.update_run(run.id, status="succeeded", finished_at=_utcnow_iso(), stats_json=json.dumps(stats))

    # Update job history
    next_run = _compute_next_run(job.schedule_expr, job.schedule_timezone)
    db.set_job_history(job_id=job_id, last_run_at=_utcnow_iso(), next_run_at=next_run)
    try:
        if isinstance(job_output_prefs, dict):
            _maybe_promote_feed_schedule(db=db, job=job, job_output_prefs=job_output_prefs)
    except Exception as exc:
        logger.debug(f"collections schedule auto-promote failed for job {job_id}: {exc}")
    return {"run_id": run.id, **stats}
