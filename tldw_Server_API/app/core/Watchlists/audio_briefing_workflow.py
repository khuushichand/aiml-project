"""Audio briefing workflow bridge.

Triggers the audio briefing workflow pipeline after a watchlist run completes,
when the job's output_prefs has generate_audio=True.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Built-in workflow definition
# ---------------------------------------------------------------------------

AUDIO_BRIEFING_WORKFLOW_DEF: dict[str, Any] = {
    "name": "audio_briefing",
    "version": 1,
    "description": "Spoken-word multi-voice audio briefing from watchlist items",
    "steps": [
        {
            "id": "compose_script",
            "type": "audio_briefing_compose",
            "config": {
                "items": "{{ inputs.items }}",
                "target_audio_minutes": "{{ inputs.target_audio_minutes }}",
                "provider": "{{ inputs.llm_provider }}",
                "model": "{{ inputs.llm_model }}",
                "multi_voice": True,
                "voice_map": "{{ inputs.voice_map }}",
            },
            "timeout_seconds": 120,
        },
        {
            "id": "clean_script",
            "type": "text_clean",
            "config": {
                "operations": [
                    "strip_markdown",
                    "normalize_whitespace",
                    "normalize_unicode",
                    "remove_urls",
                ],
            },
            "timeout_seconds": 10,
        },
        {
            "id": "generate_audio",
            "type": "multi_voice_tts",
            "config": {
                "sections": "{{ compose_script.sections }}",
                "voice_assignments": "{{ compose_script.voice_assignments }}",
                "default_model": "{{ inputs.tts_model }}",
                "default_voice": "{{ inputs.tts_voice }}",
                "response_format": "mp3",
                "speed": "{{ inputs.tts_speed }}",
                "normalize": True,
                "target_lufs": -16.0,
            },
            "timeout_seconds": 600,
            "retry": 1,
            "on_success": "_end",
            "on_failure": "tts_single_voice_fallback",
        },
        {
            "id": "tts_single_voice_fallback",
            "type": "tts",
            "config": {
                "input": "{{ compose_script.text }}",
                "model": "{{ inputs.tts_model }}",
                "voice": "{{ inputs.tts_voice }}",
                "response_format": "mp3",
                "speed": "{{ inputs.tts_speed }}",
            },
            "timeout_seconds": 600,
            "retry": 1,
        },
    ],
}


def _build_workflow_inputs(
    items: list[dict[str, Any]],
    output_prefs: dict[str, Any],
) -> dict[str, Any]:
    """Build workflow inputs dict from watchlist output_prefs."""
    return {
        "items": items,
        "target_audio_minutes": output_prefs.get("target_audio_minutes", 10),
        "tts_model": output_prefs.get("audio_model") or "kokoro",
        "tts_voice": output_prefs.get("audio_voice") or "af_heart",
        "tts_speed": output_prefs.get("audio_speed") or 1.0,
        "llm_provider": output_prefs.get("llm_provider"),
        "llm_model": output_prefs.get("llm_model"),
        "voice_map": output_prefs.get("voice_map"),
    }


async def trigger_audio_briefing(
    *,
    user_id: int,
    job_id: int,
    run_id: int,
    output_prefs: dict[str, Any],
    db: Any,
) -> str | None:
    """Trigger the audio briefing workflow for a completed watchlist run.

    Args:
        user_id: The user who owns the watchlist.
        job_id: The watchlist job ID.
        run_id: The watchlist run ID that just completed.
        output_prefs: The job's output_prefs dict.
        db: The WatchlistsDB instance.

    Returns:
        The workflow run_id if successfully enqueued, None otherwise.
    """
    if not output_prefs.get("generate_audio"):
        return None

    # Gather scraped items for this run
    try:
        scraped_items = db.list_scraped_items(
            run_id=run_id, status="ingested", limit=100
        )
    except Exception as exc:
        logger.warning(f"Audio briefing: could not load scraped items for run {run_id}: {exc}")
        return None

    if not scraped_items:
        logger.info(f"Audio briefing: no ingested items for run {run_id}, skipping")
        return None

    # Build items context (title, summary, url)
    items: list[dict[str, Any]] = []
    for item in scraped_items:
        row = item if isinstance(item, dict) else (item._asdict() if hasattr(item, "_asdict") else {})
        items.append({
            "title": row.get("title", ""),
            "summary": row.get("summary", row.get("snippet", "")),
            "url": row.get("url", row.get("source_url", "")),
        })

    workflow_inputs = _build_workflow_inputs(items, output_prefs)

    # Enqueue as a scheduler task
    try:
        from tldw_Server_API.app.core.Scheduler import get_global_scheduler
        from tldw_Server_API.app.core.Scheduler.base.task import Task

        scheduler = await get_global_scheduler()
        task = Task(
            handler="workflow_run",
            payload={
                "user_id": user_id,
                "definition_snapshot": AUDIO_BRIEFING_WORKFLOW_DEF,
                "inputs": workflow_inputs,
                "mode": "async",
                "metadata": {
                    "source": "watchlist_audio_briefing",
                    "watchlist_job_id": job_id,
                    "watchlist_run_id": run_id,
                },
            },
            timeout=3600,
            max_retries=1,
        )
        task_id = await scheduler.enqueue(task)
        logger.info(
            f"Audio briefing workflow enqueued for watchlist run {run_id}, "
            f"task_id={task_id}, items={len(items)}"
        )
        return task_id
    except Exception as exc:
        logger.warning(f"Audio briefing: failed to enqueue workflow for run {run_id}: {exc}")
        return None
