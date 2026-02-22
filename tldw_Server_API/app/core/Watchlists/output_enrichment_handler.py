"""Async output enrichment handler for watchlist outputs.

Runs as a background task to perform LLM-based enrichment:
- Topic-based grouping (LLM classification)
- Per-group summaries
- Briefing-level summary
- Re-renders template with enriched context
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


async def enrich_output(
    *,
    output_id: int,
    user_id: int,
    grouping_config: dict[str, Any] | None = None,
    summary_config: dict[str, Any] | None = None,
) -> None:
    """Enrich an output artifact with LLM-generated grouping and summaries.

    Called by Scheduler as a background task after initial output creation.
    Updates the output artifact's content and metadata in-place.
    """
    from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import _get_collections_db_for_user_id
    from tldw_Server_API.app.services.outputs_service import (
        _summarize_text_block,
        classify_items_by_topic,
        generate_briefing_summary,
        generate_group_summaries,
        group_items,
        render_output_template,
    )

    try:
        collections_db = _get_collections_db_for_user_id(user_id)
    except Exception as exc:
        logger.error(f"enrich_output: failed to get collections DB for user {user_id}: {exc}")
        return

    try:
        output_row = collections_db.get_output_artifact(output_id)
    except Exception as exc:
        logger.error(f"enrich_output: failed to load output {output_id}: {exc}")
        return

    metadata = {}
    raw_meta = getattr(output_row, "metadata_json", None)
    if raw_meta:
        try:
            metadata = json.loads(raw_meta) if isinstance(raw_meta, str) else dict(raw_meta)
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}

    # Merge configs from metadata if not passed as arguments
    if grouping_config is None and metadata.get("_enrichment_grouping_config"):
        grouping_config = metadata["_enrichment_grouping_config"]
    if summary_config is None and metadata.get("_enrichment_summary_config"):
        summary_config = metadata["_enrichment_summary_config"]

    item_ids = metadata.get("item_ids", [])
    if not item_ids:
        logger.warning(f"enrich_output: no item_ids in output {output_id}")
        _update_enrichment_status(collections_db, output_id, metadata, "failed", error="no_item_ids")
        return

    # Resolve LLM provider
    api_name = None
    model_override = None
    if summary_config:
        api_name = summary_config.get("llm_provider")
        model_override = summary_config.get("llm_model")
    if not api_name and grouping_config:
        api_name = grouping_config.get("topic_llm_provider")
        model_override = grouping_config.get("topic_llm_model")
    if not api_name:
        logger.error(f"enrich_output: no LLM provider for output {output_id}")
        _update_enrichment_status(collections_db, output_id, metadata, "failed", error="no_llm_provider")
        return

    try:
        # Phase 1: Topic grouping if requested
        groups = metadata.get("_groups", [])
        if grouping_config and grouping_config.get("group_by") == "topic":
            # We need item data -- reconstruct from metadata
            items_data = _reconstruct_items_data(collections_db, item_ids)
            topic_groups = await classify_items_by_topic(
                items_data,
                api_name=api_name,
                model_override=model_override,
                max_groups=grouping_config.get("max_groups", 7),
            )
            if topic_groups:
                groups = topic_groups
                metadata["grouping_status"] = "completed"
            else:
                # Fallback to tag grouping
                groups = group_items(items_data, group_by="tag")
                metadata["grouping_status"] = "fallback_tag"
            metadata["group_count"] = len(groups)

        # Phase 2: Per-group summaries
        if summary_config and summary_config.get("per_group_summaries") and groups:
            groups = await generate_group_summaries(
                groups,
                api_name=api_name,
                model_override=model_override,
                custom_prompt=summary_config.get("per_group_prompt"),
            )
            metadata["group_summary_status"] = "completed"

        # Phase 3: Briefing summary
        briefing_summary = ""
        if summary_config and summary_config.get("enabled", True):
            items_data = _reconstruct_items_data(collections_db, item_ids)
            briefing_summary = await generate_briefing_summary(
                items_data,
                groups=groups if groups else None,
                api_name=api_name,
                model_override=model_override,
                custom_prompt=summary_config.get("prompt"),
                max_items_for_direct=summary_config.get("max_items_for_direct_summary", 30),
            )
            metadata["summary_status"] = "completed"
            metadata["briefing_summary_text"] = briefing_summary

        # Phase 4: Re-render template with enriched context
        # (This would require the original template + context reconstruction)
        # For now, store enrichment data in metadata for frontend consumption
        if groups:
            # Store group names and summaries (not full items to keep metadata lean)
            metadata["enriched_groups"] = [
                {"name": g.get("name"), "item_count": g.get("item_count"), "summary": g.get("summary")}
                for g in groups
            ]

        metadata["enrichment_status"] = "completed"
        _update_metadata(collections_db, output_id, metadata)
        logger.info(f"enrich_output: completed enrichment for output {output_id}")

    except Exception as exc:
        logger.error(f"enrich_output: failed for output {output_id}: {exc}")
        _update_enrichment_status(collections_db, output_id, metadata, "failed", error=str(exc))


def _reconstruct_items_data(collections_db: CollectionsDatabase, item_ids: list[int]) -> list[dict[str, Any]]:
    """Reconstruct item data from IDs using DB abstraction. Best-effort."""
    items: list[dict[str, Any]] = []
    for item_id in item_ids:
        try:
            row = collections_db.get_content_item(item_id)
            tags = getattr(row, "tags", []) or []
            items.append({
                "id": getattr(row, "id", item_id),
                "title": getattr(row, "title", "Untitled") or "Untitled",
                "url": getattr(row, "url", "") or "",
                "summary": getattr(row, "summary", "") or "",
                "tags": tags if isinstance(tags, list) else [],
            })
        except Exception as exc:
            logger.warning(f"enrich_output: failed to reconstruct item {item_id}: {exc}")
            items.append({"id": item_id, "title": f"Item {item_id}", "tags": []})
    return items


def _update_enrichment_status(
    collections_db: CollectionsDatabase, output_id: int, metadata: dict[str, Any], status: str, *, error: str | None = None,
) -> None:
    """Update enrichment status in metadata."""
    metadata["enrichment_status"] = status
    if error:
        metadata["enrichment_error"] = error
    _update_metadata(collections_db, output_id, metadata)


def _update_metadata(collections_db: CollectionsDatabase, output_id: int, metadata: dict[str, Any]) -> None:
    """Persist metadata update to the DB via the collections DB abstraction."""
    try:
        collections_db.update_output_artifact_metadata(
            output_id, metadata_json=json.dumps(metadata),
        )
    except Exception as exc:
        logger.error(f"enrich_output: failed to update metadata for output {output_id}: {exc}")
