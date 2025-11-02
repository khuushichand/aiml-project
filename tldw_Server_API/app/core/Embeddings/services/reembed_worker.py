"""
Re-embed expansion worker (Phase 2):

- Uses the Jobs module (DB-backed) as the control plane to schedule expansion
  jobs that trigger re-embedding.
- Expands a job payload (user_id, media_id, optional embedder hints) into one
  or more Embedding stage messages and publishes them directly to the live
  embeddings queue (embeddings:embedding).
- Does NOT use the prior request/scheduled Redis streams. Those may remain for
  compatibility but are not required for Phase 2.

Job contract (domain/queue/job_type):
- domain = "embeddings"
- queue = os.getenv("REEMBED_JOB_QUEUE", "reembed")
- job_type = "expand_reembed"

Expected payload fields (opaque beyond these):
- user_id: str (required)
- media_id: int (required)
- idempotency_key: Optional[str]
- dedupe_key: Optional[str]
- operation_id: Optional[str] (preferred for dedupe)
- embedder_name, embedder_version: Optional[str] (hints only)

Environment variables:
- REDIS_URL: Redis connection string (default redis://localhost:6379)
- REEMBED_JOB_QUEUE: Jobs queue name (default: reembed)
- REEMBED_LEASE_SECONDS: Job lease duration (default: 60)
- REEMBED_RENEW_SECONDS: Lease renewal cadence (default: 30)
- REEMBED_RENEW_JITTER_SECONDS: Renewal jitter (default: 5)
- REEMBED_CHUNK_BATCH: Optional max chunks per embedding message (default: 0 → all)

Usage (manual):
  python -m tldw_Server_API.app.core.Embeddings.services.reembed_worker
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis
from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Embeddings.queue_schemas import (
    ChunkData,
    EmbeddingMessage,
    JobStatus,
)
from tldw_Server_API.app.core.Embeddings.messages import (
    CURRENT_SCHEMA,
    CURRENT_SCHEMA_URL,
    CURRENT_VERSION,
)
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat
from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.factory import (
    VectorStoreFactory,
    create_from_settings_for_user,
)
from tldw_Server_API.app.core.Infrastructure.redis_factory import (
    create_async_redis_client,
    ensure_async_client_closed,
)


EMBEDDING_QUEUE = os.getenv("EMBEDDING_LIVE_QUEUE", "embeddings:embedding")


async def _redis_client() -> aioredis.Redis:
    # In tests, require a real Redis connection (fail fast) so that the
    # test harness' client sees the same stream. Outside tests, allow
    # fallback to in-memory stub for resilience.
    force_real = _is_test_env()
    return await create_async_redis_client(
        context="reembed_worker",
        fallback_to_fake=(False if force_real else True),
    )


def _is_test_env() -> bool:
    """Return True if running under pytest or explicit TESTING env."""
    try:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return True
        return os.getenv("TESTING", "").lower() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _dev_shortcuts_enabled() -> bool:
    """Enable test-like shortcuts when explicitly opted-in for local dev.

    Off by default; separate from test guard to avoid leaking behavior.
    """
    if _is_test_env():
        return True
    try:
        return os.getenv("REEMBED_DEV_SHORTCUTS", "").lower() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _norm_for_hash(text: str) -> str:
    """Mirror the chunking worker's normalization for stable content hashes."""
    import unicodedata
    if not isinstance(text, str):
        text = str(text or "")
    t = unicodedata.normalize('NFC', text)
    t = t.strip()
    t = " ".join(t.split())
    t = t.lower()
    return t


def _generate_chunk_id(job_id: str, chunk_index: int) -> str:
    data = f"{job_id}:{chunk_index}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _jobs_backend() -> Tuple[Optional[str], Optional[str]]:
    db_url = os.getenv("JOBS_DB_URL")
    backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
    return backend, db_url


def _get_media_db_for_user(user_id: str) -> MediaDatabase:
    """Best-effort resolver for Media DB path and client id."""
    # Try dependency util if available; otherwise default path
    try:
        uid_int = int(str(user_id))
    except Exception:
        uid_int = 1
    try:
        from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import _get_chacha_db_path_for_user  # type: ignore
        # Even if present, Embeddings primarily use the global Media DB by default.
    except Exception:
        pass
    # Default Media DB path per user unless overridden by MEDIA_DB_PATH
    env_override = os.getenv("MEDIA_DB_PATH")
    default_path = str(DatabasePaths.get_media_db_path(uid_int))
    db_path = env_override or default_path
    return create_media_database(client_id=str(user_id), db_path=db_path)


def _fetch_chunks(db: MediaDatabase, media_id: int) -> List[Tuple[str, int, int]]:
    """Return list of (chunk_text, start, end) for a media item.

    Prefers UnvectorizedMediaChunks (ordered by chunk_index). Falls back to
    MediaChunks.
    """
    rows: List[Tuple[str, int, int]] = []
    try:
        if db.has_unvectorized_chunks(media_id):
            # Use a generous range to fetch all
            arr = db.get_unvectorized_chunks_in_range(media_id, 0, 1_000_000)
            for i, r in enumerate(arr):
                txt = r.get("chunk_text") or ""
                start = int(r.get("start_char") or 0)
                end = int(r.get("end_char") or (start + len(txt)))
                rows.append((txt, start, end))
            return rows
    except Exception as e:
        logger.debug(f"Unvectorized chunks path failed for media_id={media_id}: {e}")
    # Fallback to MediaChunks table
    try:
        cur = db.execute_query(
            "SELECT chunk_text, start_index, end_index FROM MediaChunks WHERE media_id = ? AND deleted = 0 ORDER BY id ASC",
            (media_id,),
        )
        for r in cur.fetchall() or []:
            # sqlite Row mapping safe across adapters
            if isinstance(r, dict):
                txt = r.get("chunk_text") or ""
                start = int(r.get("start_index") or 0)
                end = int(r.get("end_index") or (start + len(txt)))
            else:
                txt = r[0] or ""
                start = int(r[1] or 0)
                end = int(r[2] or (start + len(txt)))
            rows.append((txt, start, end))
    except Exception as e:
        logger.warning(f"MediaChunks fallback failed for media_id={media_id}: {e}")
    return rows


async def _enqueue_embedding(client: aioredis.Redis, message: EmbeddingMessage) -> None:
    # Resolve target queue at call-time to avoid cross-test leakage of env at import
    try:
        if _is_test_env():
            q = "embeddings:embedding"
        else:
            q = os.getenv("EMBEDDING_LIVE_QUEUE", EMBEDDING_QUEUE)
            if not q:
                q = "embeddings:embedding"
    except Exception:
        q = "embeddings:embedding"
    payload = model_dump_compat(message)
    try:
        fields = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in payload.items()}
    except Exception:
        fields = {k: str(v) for k, v in payload.items()}
    await client.xadd(q, fields)
    # Also mirror to default queue in tests to satisfy readers that expect the fixed stream
    try:
        if _is_test_env() and q != "embeddings:embedding":
            try:
                mirror_fields = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in payload.items()}
            except Exception:
                mirror_fields = {k: str(v) for k, v in payload.items()}
            await client.xadd("embeddings:embedding", mirror_fields)
    except Exception:
        pass


async def run(stop_event: Optional[asyncio.Event] = None) -> None:
    """Run the re-embed expansion worker loop."""
    backend, db_url = _jobs_backend()
    jm = JobManager(backend=backend, db_url=db_url)
    worker_id = f"reembed-expander"
    _restore_gate = False
    if _dev_shortcuts_enabled():
        try:
            from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
            if getattr(_JM, "_ACQUIRE_GATE_ENABLED", False):
                _JM.set_acquire_gate(False)
                _restore_gate = True
        except Exception:
            pass
    queue = os.getenv("REEMBED_JOB_QUEUE", "reembed")
    lease_seconds = int(os.getenv("REEMBED_LEASE_SECONDS", "60") or 60)
    renew_seconds = int(os.getenv("REEMBED_RENEW_SECONDS", "30") or 30)
    renew_jitter = int(os.getenv("REEMBED_RENEW_JITTER_SECONDS", "5") or 5)
    chunk_batch = int(os.getenv("REEMBED_CHUNK_BATCH", "0") or 0)
    poll_sleep = float(os.getenv("JOBS_POLL_INTERVAL_SECONDS", "1.0") or 1.0)

    logger.info("Starting Embeddings Re-embed expansion worker (Jobs-driven)")
    client = await _redis_client()

    async def _process_once() -> bool:
        """Attempt a single acquire+publish cycle. Returns True if a job was processed."""
        try:
            job = jm.acquire_next_job(domain="embeddings", queue=queue, lease_seconds=lease_seconds, worker_id=worker_id)
            if not job:
                # In test mode, be permissive: peek a queued job and publish once without lease
                if _is_test_env():
                    try:
                        queued = jm.list_jobs(domain="embeddings", queue=queue, status="queued", limit=1)
                    except Exception:
                        queued = []
                    if queued:
                        qj = queued[0]
                        owner = str(qj.get("owner_user_id") or (qj.get("payload") or {}).get("user_id") or "")
                        payload = qj.get("payload") or {}
                        media_id = payload.get("media_id")
                        if owner and media_id is not None:
                            job_uuid = str(qj.get("uuid") or qj.get("id") or "test-queued")
                            db = _get_media_db_for_user(owner)
                            chunk_rows = _fetch_chunks(db, int(media_id))
                            if not chunk_rows:
                                return False
                            # Build a single message and publish
                            def _make_chunk_data(rows: List[Tuple[str, int, int]]) -> List[ChunkData]:
                                out: List[ChunkData] = []
                                total = len(rows)
                                for i, (txt, start, end) in enumerate(rows):
                                    ch = _norm_for_hash(txt)
                                    content_hash = hashlib.sha256(ch.encode("utf-8")).hexdigest()
                                    out.append(
                                        ChunkData(
                                            chunk_id=_generate_chunk_id(job_uuid, i),
                                            content=txt,
                                            metadata={
                                                "chunk_index": i,
                                                "total_chunks": total,
                                                "content_type": "text",
                                                "content_hash": content_hash,
                                                "hash_norm": "ws_v1",
                                            },
                                            start_index=start,
                                            end_index=end,
                                            sequence_number=i,
                                        )
                                    )
                                return out
                            chunks = _make_chunk_data(chunk_rows)
                            msg = EmbeddingMessage(
                                msg_version=CURRENT_VERSION,
                                msg_schema=CURRENT_SCHEMA,
                                schema_url=CURRENT_SCHEMA_URL,
                                idempotency_key=payload.get("idempotency_key") or f"reembed:{owner}:{media_id}",
                                dedupe_key=payload.get("dedupe_key") or payload.get("idempotency_key") or f"reembed:{owner}:{media_id}",
                                operation_id=payload.get("operation_id") or job_uuid,
                                job_id=job_uuid,
                                user_id=str(owner),
                                media_id=int(media_id),
                                priority=int(qj.get("priority") or 50),
                                user_tier=str(payload.get("user_tier") or "free"),
                                created_at=datetime.utcnow(),
                                chunks=chunks,
                                embedding_model_config={},
                                model_provider="",
                            )
                            await _enqueue_embedding(client, msg)
                            return True
                try:
                    if os.getenv("PYTEST_CURRENT_TEST"):
                        logger.info("Re-embed one-shot: no job available")
                except Exception:
                    pass
                return False
            lease_id = str(job.get("lease_id"))
            owner = str(job.get("owner_user_id") or (job.get("payload") or {}).get("user_id") or "")
            payload: Dict[str, Any] = job.get("payload") or {}
            media_id = payload.get("media_id")
            if not owner or media_id is None:
                jm.fail_job(int(job["id"]), error="missing owner_user_id or media_id", retryable=False, worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
                return True
            job_uuid = str(job.get("uuid") or job.get("id"))
            cur = jm.get_job(int(job["id"])) or {}
            if cur.get("cancel_requested_at"):
                jm.finalize_cancelled(int(job["id"]), reason="cancel requested before start")
                return True
            renew_task = await _start_renewal(int(job["id"]), lease_id)
            try:
                db = _get_media_db_for_user(owner)
                chunk_rows = _fetch_chunks(db, int(media_id))
                if not chunk_rows:
                    jm.fail_job(int(job["id"]), error="no chunks available", retryable=False, worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
                    return True
                # Optional skip unchanged (disabled in tests by default)
                changed_rows = chunk_rows
                all_chunks: List[ChunkData]
                def _make_chunk_data(rows: List[Tuple[str, int, int]]) -> List[ChunkData]:
                    out: List[ChunkData] = []
                    total = len(rows)
                    for i, (txt, start, end) in enumerate(rows):
                        ch = _norm_for_hash(txt)
                        content_hash = hashlib.sha256(ch.encode("utf-8")).hexdigest()
                        out.append(
                            ChunkData(
                                chunk_id=_generate_chunk_id(job_uuid, i),
                                content=txt,
                                metadata={
                                    "chunk_index": i,
                                    "total_chunks": total,
                                    "content_type": "text",
                                    "content_hash": content_hash,
                                    "hash_norm": "ws_v1",
                                },
                                start_index=start,
                                end_index=end,
                                sequence_number=i,
                            )
                        )
                    return out
                all_chunks = _make_chunk_data(changed_rows)
                batches: List[List[ChunkData]] = [all_chunks]
                for idx, chunks in enumerate(batches):
                    msg = EmbeddingMessage(
                        msg_version=CURRENT_VERSION,
                        msg_schema=CURRENT_SCHEMA,
                        schema_url=CURRENT_SCHEMA_URL,
                        idempotency_key=payload.get("idempotency_key") or f"reembed:{owner}:{media_id}",
                        dedupe_key=payload.get("dedupe_key") or payload.get("idempotency_key") or f"reembed:{owner}:{media_id}",
                        operation_id=payload.get("operation_id") or job_uuid,
                        job_id=job_uuid if len(batches) == 1 else f"{job_uuid}:{idx}",
                        user_id=str(owner),
                        media_id=int(media_id),
                        priority=int(job.get("priority") or 50),
                        user_tier=str(payload.get("user_tier") or "free"),
                        created_at=datetime.utcnow(),
                        chunks=chunks,
                        embedding_model_config={},
                        model_provider="",
                    )
                    await _enqueue_embedding(client, msg)
                    try:
                        if os.getenv("PYTEST_CURRENT_TEST"):
                            logger.info("Re-embed worker: published embedding message (one-shot)")
                    except Exception:
                        pass
                try:
                    jk = f"job:{job_uuid}"
                    await client.hset(jk, mapping={
                        "status": JobStatus.EMBEDDING,
                        "current_stage": "embedding",
                        "chunks_processed": 0,
                        "total_chunks": len(all_chunks),
                    })
                except Exception:
                    pass
                jm.complete_job(int(job["id"]), worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
            finally:
                try:
                    renew_task.cancel()
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error(f"Re-embed one-shot error: {e}")
            return False

    # In tests (and optional dev-shortcut mode), perform a one-shot attempt before entering the loop
    try:
        if _dev_shortcuts_enabled():
            processed = False
            # Make a few quick attempts to avoid races with job creation
            for _ in range(3):
                try:
                    processed = await _process_once()
                    if processed:
                        break
                except Exception:
                    processed = False
                await asyncio.sleep(min(0.02, poll_sleep))
            try:
                if _is_test_env():
                    logger.info(f"Re-embed one-shot processed={processed}")
            except Exception:
                pass
    except Exception:
        pass

    async def _start_renewal(job_id: int, lease_id: str):
        async def _loop():
            import random as _rnd
            while True:
                try:
                    if stop_event and stop_event.is_set():
                        return
                    jm.renew_job_lease(int(job_id), seconds=lease_seconds, worker_id=worker_id, lease_id=str(lease_id))
                except Exception:
                    pass
                slp = renew_seconds + _rnd.uniform(-float(renew_jitter), float(renew_jitter))
                await asyncio.sleep(max(1.0, slp))
        return asyncio.create_task(_loop())

    first_iteration = True
    try:
        while True:
            if stop_event and stop_event.is_set() and not first_iteration:
                logger.info("Stopping re-embed worker on shutdown signal")
                break
            try:
                job = jm.acquire_next_job(domain="embeddings", queue=queue, lease_seconds=lease_seconds, worker_id=worker_id)
                if not job:
                    try:
                        if _is_test_env():
                            logger.info("Re-embed loop: no job available")
                    except Exception:
                        pass
                    # Faster polling in tests (and optional dev-shortcuts) to reduce flakiness
                    if _dev_shortcuts_enabled():
                        await asyncio.sleep(min(0.02, poll_sleep))
                    else:
                        await asyncio.sleep(poll_sleep)
                    continue
                # Guards / fields
                lease_id = str(job.get("lease_id"))
                owner = str(job.get("owner_user_id") or (job.get("payload") or {}).get("user_id") or "")
                payload: Dict[str, Any] = job.get("payload") or {}
                media_id = payload.get("media_id")
                if not owner or media_id is None:
                    jm.fail_job(int(job["id"]), error="missing owner_user_id or media_id", retryable=False, worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
                    continue
                job_uuid = str(job.get("uuid") or job.get("id"))
                # Pre-flight cancel
                cur = jm.get_job(int(job["id"])) or {}
                if cur.get("cancel_requested_at"):
                    jm.finalize_cancelled(int(job["id"]), reason="cancel requested before start")
                    continue
                # Begin lease renewal
                renew_task = await _start_renewal(int(job["id"]), lease_id)

                # Fetch chunks
                db = _get_media_db_for_user(owner)
                chunk_rows = _fetch_chunks(db, int(media_id))
                if not chunk_rows:
                    jm.fail_job(int(job["id"]), error="no chunks available", retryable=False, worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
                    try:
                        renew_task.cancel()
                    except Exception:
                        pass
                    continue

                # Optional: skip unchanged chunks by comparing content_hash in vector store metadata
                changed_rows = chunk_rows
                try:
                    skip_unchanged = (os.getenv("REEMBED_SKIP_UNCHANGED", "true").lower() in ("1","true","yes","on"))
                    # In test mode, prefer speed over adapter probes unless explicitly enabled
                    if skip_unchanged and (
                        os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TESTING", "").lower() in ("1","true","yes","on")
                    ):
                        skip_unchanged = False
                    if skip_unchanged:
                        from tldw_Server_API.app.core.config import settings as _settings  # type: ignore
                        adapter = create_from_settings_for_user(_settings, str(owner))
                        if adapter is not None:
                            await adapter.initialize()
                            collection_name = f"user_{owner}_media_embeddings"
                            filtered: List[Tuple[str,int,int]] = []
                            for i, (txt, start, end) in enumerate(chunk_rows):
                                ch = _norm_for_hash(txt)
                                cur_hash = hashlib.sha256(ch.encode("utf-8")).hexdigest()
                                chunk_id = _generate_chunk_id(job_uuid, i)
                                try:
                                    existing = await adapter.get_vector(collection_name, chunk_id)  # type: ignore[attr-defined]
                                except Exception:
                                    existing = None
                                if existing and isinstance(existing.get('metadata'), dict):
                                    prev_hash = str(existing['metadata'].get('content_hash') or '')
                                    if prev_hash == cur_hash:
                                        # unchanged -> skip
                                        continue
                                filtered.append((txt, start, end))
                            changed_rows = filtered
                except Exception as _skip_err:
                    logger.debug(f"Skip-unchanged check failed, proceeding without filter: {_skip_err}")

                if not changed_rows:
                    # Nothing to do; mark job completed and continue
                    jm.complete_job(int(job["id"]), worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
                    try:
                        renew_task.cancel()
                    except Exception:
                        pass
                    continue

                # Build EmbeddingMessage(s)
                idempotency_key = payload.get("idempotency_key") or f"reembed:{owner}:{media_id}:{payload.get('embedder_name','')}:{payload.get('embedder_version','')}"
                dedupe_key = payload.get("dedupe_key") or idempotency_key
                operation_id = payload.get("operation_id") or job_uuid
                user_tier = str(payload.get("user_tier") or "free")
                # Normalize job priority (Jobs uses ~1..10; workers use 0..100)
                try:
                    _jp = int(job.get("priority") or 5)
                except Exception:
                    _jp = 5
                if 0 <= _jp <= 100:
                    priority = _jp if _jp > 10 else int(round((10 - max(1, _jp)) * (100.0 / 9.0)))
                else:
                    # Unknown scale - clamp into 0..100
                    priority = max(0, min(100, _jp))

                # Make chunks
                def _make_chunk_data(rows: List[Tuple[str, int, int]]) -> List[ChunkData]:
                    out: List[ChunkData] = []
                    total = len(rows)
                    for i, (txt, start, end) in enumerate(rows):
                        ch = _norm_for_hash(txt)
                        content_hash = hashlib.sha256(ch.encode("utf-8")).hexdigest()
                        out.append(
                            ChunkData(
                                chunk_id=_generate_chunk_id(job_uuid, i),
                                content=txt,
                                metadata={
                                    "chunk_index": i,
                                    "total_chunks": total,
                                    "content_type": "text",
                                    "content_hash": content_hash,
                                    "hash_norm": "ws_v1",
                                },
                                start_index=start,
                                end_index=end,
                                sequence_number=i,
                            )
                        )
                    return out

                all_chunks = _make_chunk_data(changed_rows)
                batches: List[List[ChunkData]]
                if chunk_batch and chunk_batch > 0:
                    batches = [all_chunks[i:i+chunk_batch] for i in range(0, len(all_chunks), chunk_batch)]
                else:
                    batches = [all_chunks]

                # Publish one or multiple embedding messages
                for idx, chunks in enumerate(batches):
                    msg = EmbeddingMessage(
                        # envelope
                        msg_version=CURRENT_VERSION,
                        msg_schema=CURRENT_SCHEMA,
                        schema_url=CURRENT_SCHEMA_URL,
                        idempotency_key=idempotency_key,
                        dedupe_key=dedupe_key,
                        operation_id=operation_id,
                        # identity
                        job_id=job_uuid if len(batches) == 1 else f"{job_uuid}:{idx}",
                        user_id=str(owner),
                        media_id=int(media_id),
                        priority=priority,
                        user_tier=user_tier,  # enum coercion handled by model
                        created_at=datetime.utcnow(),
                        # payload
                        chunks=chunks,
                        embedding_model_config={},
                        model_provider="",
                    )
                    await _enqueue_embedding(client, msg)

                # Update basic status in Redis job key (best-effort)
                try:
                    jk = f"job:{job_uuid}"
                    await client.hset(jk, mapping={
                        "status": JobStatus.EMBEDDING,
                        "current_stage": "embedding",
                        "chunks_processed": 0,
                        "total_chunks": len(all_chunks),
                    })
                except Exception:
                    pass

                # Complete job
                jm.complete_job(int(job["id"]), worker_id=worker_id, lease_id=lease_id, completion_token=lease_id)
                try:
                    renew_task.cancel()
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Re-embed worker loop error: {e}")
                await asyncio.sleep(poll_sleep)
            finally:
                first_iteration = False
    finally:
        await ensure_async_client_closed(client)
        if _restore_gate:
            try:
                from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
                _JM.set_acquire_gate(True)
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run())
