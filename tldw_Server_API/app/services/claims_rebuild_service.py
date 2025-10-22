from __future__ import annotations

import threading
from queue import Queue, Empty
from dataclasses import dataclass
from typing import Optional, Dict, Any

from loguru import logger

from tldw_Server_API.app.core.Chunking import chunk_for_embedding
from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.ingestion_claims import (
    extract_claims_for_chunks,
    store_claims,
)
from tldw_Server_API.app.core.config import settings


@dataclass
class ClaimsRebuildTask:
    media_id: int
    db_path: str


class ClaimsRebuildService:
    """Background service to rebuild claims for media items."""

    def __init__(self, worker_threads: int = 1):
        self._queue: "Queue[ClaimsRebuildTask]" = Queue()
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._worker_threads = max(1, int(worker_threads))
        # Stats
        self._stats_lock = threading.Lock()
        self._stats = {"enqueued": 0, "processed": 0, "failed": 0}

    def start(self) -> None:
        if self._threads:
            return
        for i in range(self._worker_threads):
            t = threading.Thread(target=self._worker_loop, name=f"claims-rebuild-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        logger.info(f"ClaimsRebuildService started with {self._worker_threads} thread(s)")

    def stop(self) -> None:
        self._stop.set()
        for _ in self._threads:
            self._queue.put_nowait(ClaimsRebuildTask(media_id=-1, db_path=""))
        for t in self._threads:
            try:
                t.join(timeout=1.0)
            except Exception:
                pass
        self._threads.clear()
        self._stop.clear()
        stats = self.get_stats()
        logger.info(
            "ClaimsRebuildService stopped (enqueued={enq}, processed={proc}, failed={fail}, queue_len={q})",
            enq=stats.get("enqueued", 0),
            proc=stats.get("processed", 0),
            fail=stats.get("failed", 0),
            q=self._queue.qsize(),
        )

    def submit(self, media_id: int, db_path: str) -> None:
        self._queue.put_nowait(ClaimsRebuildTask(media_id=int(media_id), db_path=str(db_path)))
        with self._stats_lock:
            self._stats["enqueued"] += 1

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                task = self._queue.get(timeout=0.5)
            except Empty:
                continue
            if task.media_id < 0:
                # sentinel
                continue
            try:
                logger.debug(
                    "Processing claims rebuild task media_id={mid}, queue_size={qsize}",
                    mid=task.media_id,
                    qsize=self._queue.qsize(),
                )
                self._process_task(task)
                with self._stats_lock:
                    self._stats["processed"] += 1
            except Exception as e:
                logger.error(f"Claims rebuild failed for media_id={task.media_id}: {e}")
                with self._stats_lock:
                    self._stats["failed"] += 1
            finally:
                self._queue.task_done()

    def _process_task(self, task: ClaimsRebuildTask) -> None:
        db = create_media_database(
            client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
            db_path=task.db_path,
        )
        try:
            media = db.get_media_by_id(task.media_id, include_deleted=False, include_trash=False)
            if not media:
                logger.warning(f"Claims rebuild: media_id={task.media_id} not found")
                return
            content = media.get("content") or ""
            title = media.get("title") or f"media_{task.media_id}.txt"
            # Chunk content
            chunks = chunk_for_embedding(content, file_name=title)
            # Extract
            max_per = int(settings.get("CLAIMS_MAX_PER_CHUNK", 3))
            mode = str(settings.get("CLAIM_EXTRACTOR_MODE", "heuristic"))
            claims = extract_claims_for_chunks(chunks, extractor_mode=mode, max_per_chunk=max_per)
            if not claims:
                logger.info(f"Claims rebuild: no claims extracted for media_id={task.media_id}")
                return
            # Build map
            chunk_text_map: Dict[int, str] = {}
            for ch in chunks:
                meta = (ch or {}).get("metadata", {}) or {}
                idx = int(meta.get("chunk_index") or meta.get("index") or 0)
                chunk_text_map[idx] = (ch or {}).get("text") or (ch or {}).get("content") or ""
            # Soft delete old claims and store new
            deleted = db.soft_delete_claims_for_media(task.media_id)
            inserted = store_claims(db, media_id=task.media_id, chunk_texts_by_index=chunk_text_map, claims=claims)
            logger.info(f"Claims rebuild: media_id={task.media_id} deleted={deleted} inserted={inserted}")
        finally:
            try:
                db.close_connection()
            except Exception:
                pass

    def get_stats(self) -> Dict[str, int]:
        with self._stats_lock:
            return dict(self._stats)

    def get_queue_length(self) -> int:
        return self._queue.qsize()

    def get_worker_count(self) -> int:
        return len(self._threads)


# Module-level singleton for convenience
_service_singleton: Optional[ClaimsRebuildService] = None


def get_claims_rebuild_service() -> ClaimsRebuildService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = ClaimsRebuildService(worker_threads=1)
        _service_singleton.start()
    return _service_singleton
