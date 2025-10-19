from __future__ import annotations

import asyncio
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


DEFAULT_SNAPSHOT_PATH = Path("Databases/privilege_snapshots.json")


class PrivilegeSnapshotStore:
    """Lightweight snapshot store backed by a JSON file."""

    def __init__(self, path: Path = DEFAULT_SNAPSHOT_PATH) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._ensure_path()

    async def list_snapshots(
        self,
        *,
        page: int,
        page_size: int,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        generated_by: Optional[str],
        org_id: Optional[str],
        team_id: Optional[str],
        catalog_version: Optional[str],
        scope: Optional[str],
        include_counts: bool,
    ) -> Dict[str, Any]:
        data = await self._load()
        filtered: List[Dict[str, Any]] = []

        for entry in data:
            if org_id and entry.get("org_id") != org_id:
                continue
            if team_id and entry.get("team_id") != team_id:
                continue
            if generated_by and entry.get("generated_by") != generated_by:
                continue
            if catalog_version and entry.get("catalog_version") != catalog_version:
                continue
            generated_at = self._parse_datetime(entry.get("generated_at"))
            if date_from and generated_at and generated_at < date_from:
                continue
            if date_to and generated_at and generated_at > date_to:
                continue
            if scope:
                scope_ids = entry.get("summary", {}).get("scope_ids", [])
                if scope not in scope_ids:
                    continue
            filtered.append(entry)

        filtered.sort(
            key=lambda item: self._parse_datetime(item.get("generated_at")) or datetime.min,
            reverse=True,
        )

        total_items = len(filtered)
        page = max(page, 1)
        page_size = max(min(page_size, 200), 1)
        start = (page - 1) * page_size
        paginated = filtered[start : start + page_size]

        results: List[Dict[str, Any]] = []
        for entry in paginated:
            item = dict(entry)
            item["generated_at"] = self._parse_datetime(item.get("generated_at"))
            if not include_counts:
                item.pop("summary", None)
            results.append(item)

        return {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "items": results,
            "filters": {
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "generated_by": generated_by,
                "org_id": org_id,
                "team_id": team_id,
                "catalog_version": catalog_version,
                "scope": scope,
                "include_counts": include_counts,
            },
        }

    async def add_snapshot(self, snapshot: Dict[str, Any]) -> None:
        data = await self._load()
        snapshot_id = snapshot.get("snapshot_id")
        if not snapshot_id:
            raise ValueError("snapshot must include snapshot_id.")
        updated = False
        for idx, entry in enumerate(data):
            if entry.get("snapshot_id") == snapshot_id:
                data[idx] = snapshot
                updated = True
                break
        if not updated:
            data.append(snapshot)
        await self._write(data)

    async def clear(self) -> None:
        await self._write([])

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _ensure_path(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    async def _load(self) -> List[Dict[str, Any]]:
        async with self._lock:
            if self._cache is None:
                try:
                    contents = await asyncio.to_thread(self._path.read_text, encoding="utf-8")
                    self._cache = json.loads(contents or "[]")
                except Exception as exc:
                    logger.error("Failed to read privilege snapshot store: %s", exc)
                    self._cache = []
            # Return a shallow copy to prevent accidental mutation
            return list(self._cache)

    async def _write(self, data: List[Dict[str, Any]]) -> None:
        async with self._lock:
            try:
                payload = json.dumps(data, indent=2, default=self._serialize)
                await asyncio.to_thread(self._path.write_text, payload, encoding="utf-8")
                self._cache = list(data)
            except Exception as exc:
                logger.error("Failed to write privilege snapshot store: %s", exc)
                raise

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value


@lru_cache
def get_privilege_snapshot_store() -> PrivilegeSnapshotStore:
    return PrivilegeSnapshotStore()
