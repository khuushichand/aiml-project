from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.Collections.reading_service import ReadingService
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.services.outputs_service import (
    _build_output_filename,
    _outputs_dir_for_user,
    _resolve_output_path_for_user,
    build_items_context_from_content_items,
    render_output_template,
)


READING_DIGEST_DOMAIN = "reading"
READING_DIGEST_JOB_TYPE = "reading_digest"
READING_DIGEST_DEFAULT_LIMIT = int(os.getenv("READING_DIGEST_DEFAULT_LIMIT", "50") or "50")
READING_DIGEST_MAX_LIMIT = int(os.getenv("READING_DIGEST_MAX_LIMIT", "500") or "500")
READING_DIGEST_RETENTION_DAYS = int(os.getenv("READING_DIGEST_RETENTION_DAYS", "30") or "30")


class ReadingDigestJobError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        backoff_seconds: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        if backoff_seconds is not None:
            self.backoff_seconds = backoff_seconds


def reading_digest_queue() -> str:
    queue = (os.getenv("READING_DIGEST_JOBS_QUEUE") or "reading-digest").strip()
    return queue or "reading-digest"


def _parse_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _resolve_user_id(job: Dict[str, Any], payload: Dict[str, Any]) -> int:
    owner = job.get("owner_user_id") or payload.get("user_id")
    if owner is None or str(owner).strip() == "":
        return int(DatabasePaths.get_single_user_id())
    return int(owner)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_filters(filters: Any) -> Dict[str, Any]:
    if isinstance(filters, dict):
        return filters
    return {}


def _resolve_retention_until(retention_days: Optional[int]) -> Optional[str]:
    days = retention_days
    if days is None:
        days = max(0, int(READING_DIGEST_RETENTION_DAYS))
    if days <= 0:
        return None
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).isoformat()


def _render_default_markdown(title: str, items: list[Dict[str, Any]]) -> str:
    lines = [f"# {title}", ""]
    for idx, itm in enumerate(items, 1):
        entry_title = itm.get("title") or f"Item {idx}"
        url = itm.get("url")
        if url:
            line = f"{idx}. [{entry_title}]({url})"
        else:
            line = f"{idx}. {entry_title}"
        summary = itm.get("summary") or ""
        if summary:
            line += f" - {summary}"
        lines.append(line)
    return "\n".join(lines)


def _render_default_html(title: str, items: list[Dict[str, Any]]) -> str:
    body_parts = [f"<h1>{escape(title)}</h1>", "<ol>"]
    for idx, itm in enumerate(items, 1):
        entry_title = escape(itm.get("title") or f"Item {idx}")
        summary = escape(itm.get("summary") or "")
        url = itm.get("url")
        if url:
            entry = f'<li><a href="{escape(url)}">{entry_title}</a>'
        else:
            entry = f"<li>{entry_title}"
        if summary:
            entry += f" - {summary}"
        entry += "</li>"
        body_parts.append(entry)
    body_parts.append("</ol>")
    return "\n".join(body_parts)


def _build_reading_items_context(rows: list[Any]) -> list[Dict[str, Any]]:
    items = build_items_context_from_content_items(rows)
    for idx, row in enumerate(rows):
        try:
            items[idx]["status"] = getattr(row, "status", None)
            items[idx]["favorite"] = bool(getattr(row, "favorite", False))
            items[idx]["notes"] = getattr(row, "notes", None) or ""
            items[idx]["read_at"] = getattr(row, "read_at", None)
            items[idx]["updated_at"] = getattr(row, "updated_at", None)
        except Exception:
            continue
    return items


async def handle_reading_digest_job(job: Dict[str, Any]) -> Dict[str, Any]:
    payload = _parse_payload(job.get("payload"))
    user_id = _resolve_user_id(job, payload)
    schedule_id = payload.get("schedule_id")
    if not schedule_id:
        raise ReadingDigestJobError("reading_digest_missing_schedule", retryable=False)

    collections_db = CollectionsDatabase.for_user(user_id)
    try:
        schedule = collections_db.get_reading_digest_schedule(str(schedule_id))
    except KeyError as exc:
        raise ReadingDigestJobError("reading_digest_schedule_not_found", retryable=False) from exc

    if not schedule.enabled:
        collections_db.set_reading_digest_history(schedule.id, last_status="skipped_disabled")
        return {"status": "skipped", "reason": "disabled"}

    try:
        collections_db.set_reading_digest_history(
            schedule.id,
            last_run_at=datetime.now(timezone.utc).isoformat(),
            last_status="running",
        )
    except Exception:
        pass

    try:
        filters = _normalize_filters(schedule.filters_json)
        if isinstance(schedule.filters_json, str):
            try:
                filters = json.loads(schedule.filters_json) if schedule.filters_json else {}
            except Exception:
                filters = {}

        status = filters.get("status")
        if isinstance(status, str):
            status = [status]
        tags = filters.get("tags")
        if isinstance(tags, str):
            tags = [tags]
        favorite = filters.get("favorite")
        domain = filters.get("domain")
        q = filters.get("q")
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        sort = filters.get("sort")
        limit = _safe_int(filters.get("limit"), READING_DIGEST_DEFAULT_LIMIT)
        limit = max(1, min(READING_DIGEST_MAX_LIMIT, limit))

        service = ReadingService(user_id)
        rows, _total = service.list_items(
            status=status if isinstance(status, list) else None,
            tags=tags if isinstance(tags, list) else None,
            favorite=favorite if isinstance(favorite, bool) else None,
            q=q if isinstance(q, str) else None,
            domain=domain if isinstance(domain, str) else None,
            date_from=str(date_from) if date_from else None,
            date_to=str(date_to) if date_to else None,
            page=1,
            size=limit,
            offset=0,
            limit=limit,
            sort=sort if isinstance(sort, str) else None,
        )

        items_context = _build_reading_items_context(rows)
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        title_base = schedule.name or "Reading Digest"
        title = f"{title_base} ({generated_at})"

        output_template = None
        if schedule.template_id is not None:
            try:
                output_template = collections_db.get_output_template(int(schedule.template_id))
            except Exception:
                output_template = None
        if output_template is None and schedule.template_name:
            try:
                output_template = collections_db.get_output_template_by_name(str(schedule.template_name))
            except Exception:
                output_template = None

        output_format = (schedule.format or "").lower() or (getattr(output_template, "format", "") or "md")
        if output_format not in {"md", "html"}:
            output_format = "md"

        if output_template and output_template.format not in {"md", "html"}:
            logger.warning("reading_digest: invalid template format for %s", output_template.name)
            output_template = None

        if output_template is None:
            fallback_type = "newsletter_html" if output_format == "html" else "newsletter_markdown"
            try:
                output_template = collections_db.get_default_output_template_by_type(fallback_type)
            except Exception:
                output_template = None

        context: Dict[str, Any] = {
            "title": title,
            "generated_at": generated_at,
            "items": items_context,
            "item_count": len(items_context),
            "schedule_id": schedule.id,
            "schedule_name": schedule.name,
            "filters": filters,
        }

        if output_template:
            context["template_name"] = output_template.name
            if output_template.description:
                context["template_description"] = output_template.description
            content = render_output_template(output_template.body, context)
            output_format = (output_template.format or output_format or "md").lower()
            if output_format not in {"md", "html"}:
                output_format = "md"
        else:
            if output_format == "html":
                content = _render_default_html(title, items_context)
            else:
                content = _render_default_markdown(title, items_context)

        try:
            out_dir = _outputs_dir_for_user(user_id)
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise ReadingDigestJobError("reading_digest_storage_unavailable", retryable=False) from exc

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = _build_output_filename(title, "digest", ts, output_format)
        path = _resolve_output_path_for_user(user_id, filename)

        try:
            path.write_text(content or "", encoding="utf-8")
        except Exception as exc:
            raise ReadingDigestJobError("reading_digest_write_failed", retryable=False) from exc

        retention_until = _resolve_retention_until(schedule.retention_days)
        item_ids = [
            item_id
            for item in items_context
            for item_id in [item.get("content_item_id") or item.get("id")]
            if item_id is not None
        ]
        metadata = {
            "schedule_id": schedule.id,
            "schedule_name": schedule.name,
            "item_count": len(items_context),
            "item_ids": item_ids,
            "filters": filters,
            "format": output_format,
            "type": "reading_digest",
        }
        if output_template:
            metadata.update(
                {
                    "template_id": output_template.id,
                    "template_name": output_template.name,
                    "template_source": "outputs_templates",
                }
            )
            if output_template.description:
                metadata["template_description"] = output_template.description

        try:
            row = collections_db.create_output_artifact(
                type_="reading_digest",
                title=title,
                format_=output_format,
                storage_path=filename,
                metadata_json=json.dumps(metadata),
                job_id=job.get("id"),
                retention_until=retention_until,
            )
        except Exception as exc:
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass
            raise ReadingDigestJobError("reading_digest_db_insert_failed", retryable=False) from exc

        try:
            collections_db.set_reading_digest_history(schedule.id, last_status="succeeded")
        except Exception:
            pass

        return {
            "status": "succeeded",
            "output_id": row.id,
            "item_count": len(items_context),
        }
    except Exception as exc:
        try:
            collections_db.set_reading_digest_history(schedule.id, last_status="error")
        except Exception:
            pass
        raise
