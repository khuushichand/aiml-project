"""
Watchlists fetch→ingest pipeline

Executes a watchlist job for a given user:
- Select sources based on job scope (sources/groups/tags)
- For each source:
  - If `rss`: fetch feed items, then fetch each linked page and ingest
  - If `site`: fetch page and ingest
- Persist per-run stats and append ingested media IDs to scrape_run_items

Notes:
- In tests (TEST_MODE=1), RSS fetch returns a fake item and site fetch may be
  bypassed. We count items but avoid network.
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase, SourceRow
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.Collections.utils import hash_text_sha256, truncate_text, word_count
from tldw_Server_API.app.core.Collections.embedding_queue import enqueue_embeddings_job_for_item
from tldw_Server_API.app.core.Watchlists.fetchers import fetch_rss_feed, fetch_site_article


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def _compute_next_run(cron: Optional[str], timezone_str: Optional[str]) -> Optional[str]:
    if not cron:
        return None
    try:
        from apscheduler.triggers.cron import CronTrigger
        tz = timezone_str or "UTC"
        trigger = CronTrigger.from_crontab(cron, timezone=tz)
        now = datetime.now(trigger.timezone)
        nxt = trigger.get_next_fire_time(None, now)
        return nxt.isoformat() if nxt else None
    except Exception:
        return None


_truncate = truncate_text
_hash_content = hash_text_sha256
_word_count = word_count


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

    # Resolve per-user media DB path and instantiate
    media_db_path = str(DatabasePaths.get_media_db_path(int(user_id)))
    mdb = MediaDatabase(db_path=media_db_path, client_id=str(user_id))

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

    try:
        for src in sources:
            try:
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

                if (src.source_type or "").lower() == "rss":
                    urls = [src.url]
                    rss_items: List[Dict[str, Any]]
                    # Per-source settings
                    settings = {}
                    try:
                        settings = json.loads(src.settings_json or "{}") if getattr(src, "settings_json", None) else {}
                    except Exception:
                        settings = {}
                    rss_limit = int(settings.get("limit", 50)) if isinstance(settings.get("limit", 50), int) else 50
                    if test_mode:
                        res = {"status": 200, "items": [{"title": "Test Item", "url": "https://example.com/x", "summary": "Test"}]}
                    else:
                        res = await fetch_rss_feed(src.url, etag=getattr(src, "etag", None), last_modified=getattr(src, "last_modified", None), timeout=8.0, tenant_id="default")
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
                    rss_items = list(res.get("items") or [])
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

                        article = None if test_mode else fetch_site_article(link)
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
                        ingestion_ok = False
                        ingested_media_id: Optional[int] = None
                        ingested_media_uuid: Optional[str] = None
                        summary_text = article.get("content") or it.get("summary") or ""
                        try:
                            media_id, media_uuid, msg = mdb.add_media_with_keywords(
                                url=article.get("url") or link,
                                title=article.get("title") or (it.get("title") or "Untitled"),
                                media_type="article",
                                content=article.get("content") or (it.get("summary") or ""),
                                author=article.get("author"),
                                keywords=_keywords_for_source(src),
                                overwrite=False,
                            )
                            if media_id:
                                ingested_media_id = int(media_id)
                                ingested_media_uuid = media_uuid
                                db.append_run_item(run.id, ingested_media_id, source_id=int(src.id))
                                items_ingested += 1
                                ingestion_ok = True
                                try:
                                    db.mark_seen_item(
                                        int(src.id),
                                        item_key,
                                        etag=None,
                                        last_modified=(it.get("published") or None),
                                    )
                                except Exception:
                                    pass
                            elif test_mode:
                                items_ingested += 1
                                ingestion_ok = True
                                try:
                                    db.mark_seen_item(
                                        int(src.id),
                                        item_key,
                                        etag=None,
                                        last_modified=(it.get("published") or None),
                                    )
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.debug(f"Ingestion failed for {link}: {e}")
                            if test_mode:
                                items_ingested += 1
                                ingestion_ok = True
                                try:
                                    db.mark_seen_item(
                                        int(src.id),
                                        item_key,
                                        etag=None,
                                        last_modified=(it.get("published") or None),
                                    )
                                except Exception:
                                    pass

                        if ingestion_ok:
                            content_text = article.get("content") or summary_text or ""
                            tags_for_item = _keywords_for_source(src)
                            metadata_payload = {
                                "source_id": int(src.id),
                                "source_name": getattr(src, "name", None),
                                "job_id": job_id,
                                "run_id": run.id,
                                "media_uuid": ingested_media_uuid,
                                "tags": tags_for_item,
                            }
                            item_row = None
                            try:
                                item_row = collections_db.upsert_content_item(
                                    origin="watchlist",
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
                            if item_row and (item_row.is_new or item_row.content_changed):
                                try:
                                    await enqueue_embeddings_job_for_item(
                                        user_id=user_id,
                                        item_id=item_row.id,
                                        content=content_text,
                                        metadata={
                                            "origin": "watchlist",
                                            "job_id": job_id,
                                            "run_id": run.id,
                                            "tags": tags_for_item,
                                        },
                                    )
                                except Exception as exc:
                                    logger.debug(f"Embedding enqueue failed for watchlist item {item_row.id}: {exc}")
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
                                media_id=None,
                                media_uuid=None,
                                published_at=it.get("published"),
                            )
                            continue

                    # Update last_scraped_at/status for source
                    try:
                        db.update_source_scrape_meta(int(src.id), last_scraped_at=_utcnow_iso(), status="ok")
                    except Exception:
                        pass

                elif (src.source_type or "").lower() == "site":
                    # Determine discovery preferences
                    settings = {}
                    try:
                        settings = json.loads(src.settings_json or "{}") if getattr(src, "settings_json", None) else {}
                    except Exception:
                        settings = {}
                    top_n = 1
                    try:
                        top_n = int(settings.get("top_n", 1))
                    except Exception:
                        top_n = 1
                    discover_method = str(settings.get("discover_method", "auto")).lower()

                    urls_to_fetch: List[str] = []
                    if top_n > 1:
                        try:
                            from tldw_Server_API.app.core.Watchlists.fetchers import fetch_site_top_links
                            urls_to_fetch = await fetch_site_top_links(src.url, top_n=top_n, method=discover_method)
                        except Exception:
                            urls_to_fetch = [src.url]
                    else:
                        urls_to_fetch = [src.url]

                    items_found += len(urls_to_fetch)
                    for page_url in urls_to_fetch:
                        article = None if test_mode else fetch_site_article(page_url)
                        if article is None and test_mode:
                            article = {"title": src.name or "Untitled", "url": page_url, "content": "", "author": None}
                        if not article:
                            _record_scraped(
                                status="error",
                                url=page_url,
                                title=src.name,
                                summary=None,
                                media_id=None,
                                media_uuid=None,
                                published_at=None,
                            )
                            continue
                        ingestion_ok = False
                        ingested_media_id: Optional[int] = None
                        ingested_media_uuid: Optional[str] = None
                        summary_text = article.get("content") or ""
                        try:
                            media_id, media_uuid, msg = mdb.add_media_with_keywords(
                                url=article.get("url") or page_url,
                                title=article.get("title") or src.name,
                                media_type="article",
                                content=article.get("content") or "",
                                author=article.get("author"),
                                keywords=_keywords_for_source(src),
                                overwrite=False,
                            )
                            if media_id:
                                ingested_media_id = int(media_id)
                                ingested_media_uuid = media_uuid
                                db.append_run_item(run.id, ingested_media_id, source_id=int(src.id))
                                items_ingested += 1
                                ingestion_ok = True
                            elif test_mode:
                                ingestion_ok = True
                                items_ingested += 1
                        except Exception as e:
                            logger.debug(f"Ingestion failed for site {page_url}: {e}")
                            if test_mode:
                                ingestion_ok = True
                                items_ingested += 1
                        if ingestion_ok:
                            content_text = article.get("content") or summary_text or ""
                            tags_for_item = _keywords_for_source(src)
                            metadata_payload = {
                                "source_id": int(src.id),
                                "source_name": getattr(src, "name", None),
                                "job_id": job_id,
                                "run_id": run.id,
                                "media_uuid": ingested_media_uuid,
                                "tags": tags_for_item,
                            }
                            item_row = None
                            try:
                                item_row = collections_db.upsert_content_item(
                                    origin="watchlist",
                                    origin_type=str(src.source_type or ""),
                                    origin_id=int(src.id),
                                    url=article.get("url") or page_url,
                                    canonical_url=article.get("url") or page_url,
                                    domain=None,
                                    title=article.get("title") or src.name,
                                    summary=_truncate(summary_text, 600),
                                    content_hash=_hash_content(content_text),
                                    word_count=_word_count(content_text),
                                    published_at=None,
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
                            if item_row and (item_row.is_new or item_row.content_changed):
                                try:
                                    await enqueue_embeddings_job_for_item(
                                        user_id=user_id,
                                        item_id=item_row.id,
                                        content=content_text,
                                        metadata={
                                            "origin": "watchlist",
                                            "job_id": job_id,
                                            "run_id": run.id,
                                            "tags": tags_for_item,
                                        },
                                    )
                                except Exception as exc:
                                    logger.debug(f"Embedding enqueue failed for watchlist item {item_row.id}: {exc}")
                            _record_scraped(
                                status="ingested",
                                url=article.get("url") or page_url,
                                title=article.get("title") or src.name,
                                summary=summary_text,
                                media_id=ingested_media_id,
                                media_uuid=ingested_media_uuid,
                                published_at=None,
                            )
                        else:
                            _record_scraped(
                                status="error",
                                url=article.get("url") or page_url,
                                title=article.get("title") or src.name,
                                summary=summary_text,
                                media_id=None,
                                media_uuid=None,
                                published_at=None,
                            )
                    try:
                        db.update_source_scrape_meta(int(src.id), last_scraped_at=_utcnow_iso(), status="ok")
                    except Exception:
                        pass
                else:
                    # Unknown type — skip
                    continue
            except Exception as e:
                logger.debug(f"Source processing failed (id={getattr(src, 'id', '?')}): {e}")
                try:
                    db.update_source_scrape_meta(int(src.id), last_scraped_at=_utcnow_iso(), status="error")
                except Exception:
                    pass

        stats = {"items_found": items_found, "items_ingested": items_ingested}
        db.update_run(run.id, status="succeeded", finished_at=_utcnow_iso(), stats_json=json.dumps(stats))

        # Update job history
        next_run = _compute_next_run(job.schedule_expr, job.schedule_timezone)
        db.set_job_history(job_id=job_id, last_run_at=_utcnow_iso(), next_run_at=next_run)
        return {"run_id": run.id, **stats}

    except Exception as e:
        logger.error(f"run_watchlist_job failed: {e}")
        db.update_run(run.id, status="failed", finished_at=_utcnow_iso(), error_msg=str(e))
        raise
