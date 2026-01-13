from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import io
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class ReadingImportItem:
    url: str
    title: Optional[str]
    tags: List[str]
    status: Optional[str]
    favorite: bool
    notes: Optional[str]
    read_at: Optional[str]
    metadata: Dict[str, Any]


def detect_import_source(filename: Optional[str], raw_bytes: bytes) -> str:
    if filename:
        lowered = filename.lower()
        if lowered.endswith(".json"):
            return "pocket"
        if lowered.endswith(".csv"):
            return "instapaper"
    try:
        json.loads(raw_bytes.decode("utf-8"))
        return "pocket"
    except Exception:
        return "instapaper"


def parse_reading_import(raw_bytes: bytes, *, source: str, filename: Optional[str] = None) -> List[ReadingImportItem]:
    if source == "auto":
        source = detect_import_source(filename, raw_bytes)
    if source == "pocket":
        return parse_pocket_export(raw_bytes)
    if source == "instapaper":
        return parse_instapaper_export(raw_bytes)
    raise ValueError("unsupported_import_source")


def parse_pocket_export(raw_bytes: bytes) -> List[ReadingImportItem]:
    text = raw_bytes.decode("utf-8", errors="replace")
    payload = json.loads(text)
    items_obj = payload.get("list")
    if isinstance(items_obj, list):
        items = items_obj
    elif isinstance(items_obj, dict):
        items = list(items_obj.values())
    else:
        items = []

    parsed: List[ReadingImportItem] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        url = entry.get("resolved_url") or entry.get("given_url") or entry.get("url")
        if not url:
            continue
        title = entry.get("resolved_title") or entry.get("given_title") or entry.get("title")
        tags = _normalize_tags(entry.get("tags"))
        status = _map_pocket_status(entry.get("status"))
        if status == "deleted":
            continue
        favorite = _truthy(entry.get("favorite"))
        read_at = _parse_epoch(entry.get("time_read"))
        if read_at:
            status = "read"
        notes = entry.get("excerpt") or entry.get("note") or None
        metadata: Dict[str, Any] = {
            "import_source": "pocket",
        }
        added_at = _parse_epoch(entry.get("time_added"))
        if added_at:
            metadata["import_added_at"] = added_at
        parsed.append(
            ReadingImportItem(
                url=str(url),
                title=str(title) if title else None,
                tags=tags,
                status=status or "saved",
                favorite=favorite,
                notes=str(notes) if notes else None,
                read_at=read_at,
                metadata=metadata,
            )
        )
    return parsed


def parse_instapaper_export(raw_bytes: bytes) -> List[ReadingImportItem]:
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    parsed: List[ReadingImportItem] = []
    for row in reader:
        if not row:
            continue
        normalized = {(_normalize_header(k)): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        url = normalized.get("url") or normalized.get("link")
        if not url:
            continue
        title = normalized.get("title")
        tags = _split_tags(normalized.get("tags"))
        notes = normalized.get("notes") or normalized.get("selection") or None
        folder = (normalized.get("folder") or normalized.get("state") or "").lower()
        status = "archived" if "archive" in folder else "saved"
        favorite = "star" in folder
        metadata: Dict[str, Any] = {
            "import_source": "instapaper",
        }
        added_raw = normalized.get("added") or normalized.get("timestamp") or normalized.get("time")
        if added_raw:
            metadata["import_added_at"] = added_raw
        parsed.append(
            ReadingImportItem(
                url=str(url),
                title=str(title) if title else None,
                tags=tags,
                status=status,
                favorite=favorite,
                notes=str(notes) if notes else None,
                read_at=None,
                metadata=metadata,
            )
        )
    return parsed


def _normalize_header(value: str) -> str:
    return value.strip().lower()


def _split_tags(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _normalize_tags(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        tags = []
        for entry in value:
            if isinstance(entry, dict):
                tag = entry.get("tag") or entry.get("name")
                if tag:
                    tags.append(str(tag))
            elif entry:
                tags.append(str(entry))
        return sorted({t.strip().lower() for t in tags if t})
    if isinstance(value, dict):
        return sorted({str(k).strip().lower() for k in value.keys() if k})
    if isinstance(value, str):
        return _split_tags(value)
    return []


def _map_pocket_status(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if text == "0":
        return "saved"
    if text == "1":
        return "archived"
    if text == "2":
        return "deleted"
    return "saved"


def _parse_epoch(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        ivalue = int(value)
    except Exception:
        return None
    if ivalue <= 0:
        return None
    return datetime.fromtimestamp(ivalue, tz=timezone.utc).replace(microsecond=0).isoformat()


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "true", "yes"}


def normalize_import_items(items: Iterable[ReadingImportItem]) -> List[ReadingImportItem]:
    return [item for item in items if item.url]
