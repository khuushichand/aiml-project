"""
Adapter to normalize external Block payloads into {text, metadata} chunks.
"""

from collections.abc import Sequence
from dataclasses import asdict as dataclass_asdict
from dataclasses import is_dataclass
from typing import Any, Optional

from tldw_Server_API.app.core.Chunking import Chunker

from .chunk_metadata import CitationSpan, RAGChunkMetadata, model_dump_compat


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return dataclass_asdict(value)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()  # type: ignore[call-arg]
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return value.dict()  # type: ignore[call-arg]
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return dict(value.__dict__)
        except Exception:
            pass
    return {}


def _get_value(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source and source.get(key) is not None:
            return source.get(key)
    return None


def _get_dict(source: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            return value
        coerced = _as_dict(value)
        if coerced:
            return coerced
    return {}


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            try:
                return int(stripped)
            except Exception:
                return None
    return None


def _coerce_str_list(value: Any) -> Optional[list[str]]:
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, tuple):
        return [str(v) for v in value if v is not None]
    return None


def _normalize_timestamp_ms(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        num = float(value)
    except Exception:
        return None
    if num < 0:
        return None
    if isinstance(value, float) and not num.is_integer():
        return int(num * 1000)
    if num < 1e7:
        return int(num * 1000)
    return int(num)


def _normalize_bbox_quad(value: Any) -> Optional[list[dict[str, float]]]:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("bbox_quad") or value.get("bbox") or value.get("points")
    if not isinstance(value, (list, tuple)):
        return None
    points: list[dict[str, float]] = []
    if len(value) == 4 and all(isinstance(v, (int, float)) for v in value):
        x0, y0, x1, y1 = [float(v) for v in value]
        points = [
            {"x": x0, "y": y0},
            {"x": x1, "y": y0},
            {"x": x1, "y": y1},
            {"x": x0, "y": y1},
        ]
    else:
        for item in value:
            if isinstance(item, dict):
                x = item.get("x")
                y = item.get("y")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                x, y = item[0], item[1]
            else:
                continue
            try:
                points.append({"x": float(x), "y": float(y)})
            except Exception:
                continue
    if not points:
        return None
    return points[:4]


def _normalize_block_type(value: Any) -> str:
    if value is None:
        return "text"
    try:
        raw = str(value).strip().upper()
    except Exception:
        return "text"
    mapping = {
        "TEXT": "text",
        "PARAGRAPH": "text",
        "TEXTSECTION": "text",
        "HEADING": "heading",
        "HEADER": "heading",
        "TITLE": "heading",
        "TABLE": "table",
        "TABLE_ROW": "table",
        "TABLE_CELL": "table",
        "BULLET_LIST": "list",
        "NUMBERED_LIST": "list",
        "LIST": "list",
        "LIST_ITEM": "list",
        "CODE": "code",
        "CODE_BLOCK": "code",
        "IMAGE": "media",
        "VIDEO": "media",
        "AUDIO": "media",
        "FILE": "media",
    }
    mapped = mapping.get(raw, raw.lower())
    return Chunker.normalize_chunk_type(mapped) or "text"


def _extract_text(payload: dict[str, Any]) -> Optional[str]:
    text = _get_value(payload, "text", "content", "value", "chunk_text")
    if text is None:
        items = _get_value(payload, "items", "list_items")
        if isinstance(items, (list, tuple)):
            text = "\n".join(str(item) for item in items if item is not None)
    if text is None:
        rows = _get_value(payload, "rows", "table", "cells")
        if isinstance(rows, (list, tuple)):
            row_texts = []
            for row in rows:
                if isinstance(row, (list, tuple)):
                    row_texts.append(" | ".join(str(cell) for cell in row))
                else:
                    row_texts.append(str(row))
            text = "\n".join(row_texts)
    if text is None:
        return None
    return str(text)


def _build_citation_span(payload: dict[str, Any], meta: dict[str, Any]) -> Optional[CitationSpan]:
    def pick(*keys: str) -> Any:
        for key in keys:
            if key in payload and payload.get(key) is not None:
                return payload.get(key)
            if key in meta and meta.get(key) is not None:
                return meta.get(key)
        return None

    page_number = _coerce_int(pick("page_number", "page", "page_no"))
    paragraph_number = _coerce_int(pick("paragraph_number", "paragraph"))
    line_number = _coerce_int(pick("line_number"))
    slide_number = _coerce_int(pick("slide_number"))
    row_number = _coerce_int(pick("row_number", "row"))
    column_number = _coerce_int(pick("column_number", "col", "column"))
    sheet_name = pick("sheet_name")

    start_ts_ms = _coerce_int(pick("start_timestamp_ms", "start_ts_ms"))
    if start_ts_ms is None:
        start_ts_ms = _normalize_timestamp_ms(pick("start_timestamp", "start_ts"))
    end_ts_ms = _coerce_int(pick("end_timestamp_ms", "end_ts_ms"))
    if end_ts_ms is None:
        end_ts_ms = _normalize_timestamp_ms(pick("end_timestamp", "end_ts"))

    bbox_raw = pick("bbox_quad", "bbox", "bounding_box", "boundingBox")
    bbox_quad = _normalize_bbox_quad(bbox_raw)

    if not any(
        [
            page_number,
            paragraph_number,
            line_number,
            slide_number,
            row_number,
            column_number,
            sheet_name,
            start_ts_ms,
            end_ts_ms,
            bbox_quad,
        ]
    ):
        return None

    return CitationSpan(
        page_number=page_number,
        paragraph_number=paragraph_number,
        line_number=line_number,
        slide_number=slide_number,
        row_number=row_number,
        column_number=column_number,
        sheet_name=str(sheet_name) if sheet_name is not None else None,
        start_timestamp_ms=start_ts_ms,
        end_timestamp_ms=end_ts_ms,
        bbox_quad=bbox_quad,
    )


def block_to_chunks(blocks: Sequence[Any]) -> list[dict[str, Any]]:
    """Convert external Block payloads into normalized chunks."""
    output: list[dict[str, Any]] = []
    for block in blocks or []:
        block_dict = _as_dict(block)
        if not block_dict:
            continue

        text = _extract_text(block_dict)
        if text is None:
            continue

        block_meta = _get_dict(block_dict, "metadata", "meta")
        code_meta = _get_dict(block_dict, "code_metadata", "codeMetadata", "code")
        list_meta = _get_dict(block_dict, "list_metadata", "listMetadata", "list")
        table_meta = _get_dict(block_dict, "table_metadata", "tableMetadata", "table")
        citation_meta = _get_dict(block_dict, "citation", "citation_metadata", "citationMetadata")

        block_type_raw = _get_value(block_dict, "block_type", "blockType", "type", "kind")
        chunk_type = _normalize_block_type(block_type_raw)

        metadata_payload: dict[str, Any] = {
            "chunk_type": chunk_type,
            "media_id": _get_value(block_dict, "media_id", "mediaId"),
            "file_name": _get_value(block_dict, "file_name", "fileName"),
            "chunk_index": _coerce_int(_get_value(block_dict, "chunk_index", "chunkIndex")),
            "total_chunks": _coerce_int(_get_value(block_dict, "total_chunks", "totalChunks")),
            "start_char": _coerce_int(_get_value(block_dict, "start_char", "start_index", "start_offset")),
            "end_char": _coerce_int(_get_value(block_dict, "end_char", "end_index", "end_offset")),
            "section_path": _get_value(block_meta, "section_path", "sectionPath"),
            "ancestry_titles": _coerce_str_list(_get_value(block_meta, "ancestry_titles", "ancestryTitles")),
            "language": _get_value(block_meta, "language"),
            "context_header": _get_value(block_meta, "context_header", "contextHeader"),
            "contextual_summary_ref": _get_value(block_meta, "contextual_summary_ref", "contextualSummaryRef"),
        }

        code_language = _get_value(code_meta, "language") or _get_value(block_meta, "code_language", "codeLanguage")
        if code_language:
            metadata_payload["code_language"] = str(code_language)

        list_style = _get_value(list_meta, "list_style", "listStyle", "style") or _get_value(
            block_meta, "list_style", "listStyle"
        )
        if list_style:
            metadata_payload["list_style"] = str(list_style)

        table_row = _coerce_int(_get_value(table_meta, "row", "row_index", "table_row")) or _coerce_int(
            _get_value(block_meta, "table_row")
        )
        table_col = _coerce_int(_get_value(table_meta, "col", "column", "column_index", "table_col")) or _coerce_int(
            _get_value(block_meta, "table_col")
        )
        if table_row is not None:
            metadata_payload["table_row"] = table_row
        if table_col is not None:
            metadata_payload["table_col"] = table_col

        citation_span = _build_citation_span(citation_meta, {**block_meta, **block_dict})
        if citation_span is not None:
            metadata_payload["citation"] = citation_span

        metadata_model = RAGChunkMetadata(**metadata_payload)
        output.append(
            {
                "text": text,
                "metadata": model_dump_compat(metadata_model),
            }
        )
    return output


__all__ = ["block_to_chunks"]

