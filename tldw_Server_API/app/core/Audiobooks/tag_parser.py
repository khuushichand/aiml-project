"""Utilities for parsing timestamped tag markers in audiobook text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import ChapterPreview

_TAG_LINE_RE = re.compile(r"^\[\[(.+)\]\]$")
_CHAPTER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class ChapterMarker:
    offset: int
    chapter_id: str | None
    title: str | None


@dataclass(frozen=True)
class ScalarMarker:
    offset: int
    value: str


@dataclass(frozen=True)
class SpeedMarker:
    offset: int
    value: float


@dataclass(frozen=True)
class TimestampMarker:
    offset: int
    time_ms: int


@dataclass
class TagParseResult:
    clean_text: str
    chapter_markers: list[ChapterMarker]
    voice_markers: list[ScalarMarker]
    speed_markers: list[SpeedMarker]
    ts_markers: list[TimestampMarker]
    warnings: list[str]

    def as_metadata(self) -> dict:
        return {
            "chapter_markers": [
                {"offset": m.offset, "chapter_id": m.chapter_id, "title": m.title}
                for m in self.chapter_markers
            ],
            "voice_markers": [{"offset": m.offset, "value": m.value} for m in self.voice_markers],
            "speed_markers": [{"offset": m.offset, "value": m.value} for m in self.speed_markers],
            "ts_markers": [{"offset": m.offset, "time_ms": m.time_ms} for m in self.ts_markers],
            "warnings": list(self.warnings),
        }


def parse_tagged_text(text: str) -> TagParseResult:
    clean_parts: list[str] = []
    chapter_markers: list[ChapterMarker] = []
    voice_markers: list[ScalarMarker] = []
    speed_markers: list[SpeedMarker] = []
    ts_markers: list[TimestampMarker] = []
    warnings: list[str] = []

    pending_chapter_offset: int | None = None
    pending_chapter_id: str | None = None
    pending_chapter_title: str | None = None

    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        tag_match = _TAG_LINE_RE.match(stripped)
        if tag_match:
            content = tag_match.group(1).strip()
            if "=" not in content:
                warnings.append(f"tag_missing_value:{content}")
                continue
            key_part, value = content.split("=", 1)
            key_part = key_part.strip()
            value = value.strip()
            key = key_part
            attr = None
            if ":" in key_part:
                key, attr = key_part.split(":", 1)
            key = key.strip().lower()
            if attr is not None:
                attr = attr.strip().lower()
            if key == "chapter":
                if pending_chapter_offset is None:
                    pending_chapter_offset = offset
                if attr == "id":
                    if _CHAPTER_ID_RE.match(value):
                        pending_chapter_id = value
                    else:
                        warnings.append(f"invalid_chapter_id:{value}")
                elif attr == "title":
                    if len(value) <= 128:
                        pending_chapter_title = value
                    else:
                        warnings.append("chapter_title_too_long")
                else:
                    warnings.append(f"unknown_chapter_attr:{attr}")
            elif key == "voice":
                if value:
                    voice_markers.append(ScalarMarker(offset=offset, value=value))
            elif key == "speed":
                try:
                    speed_value = float(value)
                    speed_markers.append(SpeedMarker(offset=offset, value=speed_value))
                except ValueError:
                    warnings.append(f"invalid_speed:{value}")
            elif key == "ts":
                time_ms = _parse_timestamp_ms(value)
                if time_ms is None:
                    warnings.append(f"invalid_ts:{value}")
                else:
                    ts_markers.append(TimestampMarker(offset=offset, time_ms=time_ms))
            else:
                warnings.append(f"unknown_tag:{key}")
            continue

        if pending_chapter_offset is not None:
            chapter_markers.append(
                ChapterMarker(
                    offset=pending_chapter_offset,
                    chapter_id=pending_chapter_id,
                    title=pending_chapter_title,
                )
            )
            pending_chapter_offset = None
            pending_chapter_id = None
            pending_chapter_title = None

        clean_parts.append(line)
        offset += len(line)

    if pending_chapter_offset is not None:
        warnings.append("chapter_tag_without_text")

    return TagParseResult(
        clean_text="".join(clean_parts),
        chapter_markers=chapter_markers,
        voice_markers=voice_markers,
        speed_markers=speed_markers,
        ts_markers=ts_markers,
        warnings=warnings,
    )


def build_chapters_from_markers(text: str, markers: list[ChapterMarker]) -> list[ChapterPreview]:
    if not markers:
        return []
    length = len(text)
    ordered = sorted(markers, key=lambda m: m.offset)
    chapters: list[ChapterPreview] = []
    for idx, marker in enumerate(ordered):
        start = max(0, min(marker.offset, length))
        next_offset = length
        if idx + 1 < len(ordered):
            next_offset = max(0, min(ordered[idx + 1].offset, length))
        if start >= next_offset:
            continue
        chapter_text = text[start:next_offset]
        chapter_id = marker.chapter_id or f"ch_{len(chapters) + 1:03d}"
        chapters.append(
            ChapterPreview(
                chapter_id=chapter_id,
                title=marker.title,
                start_offset=start,
                end_offset=next_offset,
                word_count=max(1, len(chapter_text.split())),
            )
        )
    return chapters


def _parse_timestamp_ms(value: str) -> int | None:
    match = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})\.(\d{1,3})$", value)
    if not match:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int(match.group(4).ljust(3, "0"))
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis
