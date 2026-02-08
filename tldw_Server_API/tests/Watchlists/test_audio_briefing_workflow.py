"""Tests for audio briefing workflow bridge.

Tests the trigger function, workflow input construction, and workflow definition.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestAudioBriefingWorkflowDefinition:
    """Tests for the built-in workflow definition."""

    def test_workflow_def_has_required_steps(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            AUDIO_BRIEFING_WORKFLOW_DEF,
        )

        step_ids = [s["id"] for s in AUDIO_BRIEFING_WORKFLOW_DEF["steps"]]
        assert "compose_script" in step_ids
        assert "clean_script" in step_ids
        assert "generate_audio" in step_ids

    def test_workflow_def_step_types(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            AUDIO_BRIEFING_WORKFLOW_DEF,
        )

        steps = AUDIO_BRIEFING_WORKFLOW_DEF["steps"]
        step_types = {s["id"]: s["type"] for s in steps}
        assert step_types["compose_script"] == "audio_briefing_compose"
        assert step_types["clean_script"] == "text_clean"
        assert step_types["generate_audio"] == "multi_voice_tts"

    def test_workflow_def_has_timeouts(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            AUDIO_BRIEFING_WORKFLOW_DEF,
        )

        for step in AUDIO_BRIEFING_WORKFLOW_DEF["steps"]:
            assert "timeout_seconds" in step, f"Step {step['id']} missing timeout"


class TestBuildWorkflowInputs:
    """Tests for _build_workflow_inputs."""

    def test_default_inputs(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            _build_workflow_inputs,
        )

        items = [{"title": "Test", "summary": "Summary"}]
        output_prefs = {"generate_audio": True}

        inputs = _build_workflow_inputs(items, output_prefs)

        assert inputs["items"] == items
        assert inputs["target_audio_minutes"] == 10
        assert inputs["tts_model"] == "kokoro"
        assert inputs["tts_voice"] == "af_heart"
        assert inputs["tts_speed"] == 1.0
        assert inputs["llm_provider"] is None
        assert inputs["llm_model"] is None
        assert inputs["voice_map"] is None

    def test_custom_inputs(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            _build_workflow_inputs,
        )

        items = [{"title": "News", "summary": "Story"}]
        output_prefs = {
            "generate_audio": True,
            "target_audio_minutes": 5,
            "audio_model": "tts-1",
            "audio_voice": "nova",
            "audio_speed": 1.2,
            "llm_provider": "openai",
            "llm_model": "gpt-4o",
            "voice_map": {"HOST": "af_bella"},
        }

        inputs = _build_workflow_inputs(items, output_prefs)

        assert inputs["target_audio_minutes"] == 5
        assert inputs["tts_model"] == "tts-1"
        assert inputs["tts_voice"] == "nova"
        assert inputs["tts_speed"] == 1.2
        assert inputs["llm_provider"] == "openai"
        assert inputs["llm_model"] == "gpt-4o"
        assert inputs["voice_map"] == {"HOST": "af_bella"}


class TestTriggerAudioBriefing:
    """Tests for trigger_audio_briefing."""

    @pytest.mark.asyncio
    async def test_trigger_skips_when_generate_audio_false(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            trigger_audio_briefing,
        )

        result = await trigger_audio_briefing(
            user_id=1,
            job_id=1,
            run_id=1,
            output_prefs={"generate_audio": False},
            db=MagicMock(),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_skips_when_no_items(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            trigger_audio_briefing,
        )

        db = MagicMock()
        db.list_scraped_items.return_value = []

        result = await trigger_audio_briefing(
            user_id=1,
            job_id=1,
            run_id=1,
            output_prefs={"generate_audio": True},
            db=db,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_enqueues_workflow(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            trigger_audio_briefing,
        )

        db = MagicMock()
        db.list_scraped_items.return_value = [
            {"title": "Story 1", "summary": "Summary 1", "url": "https://example.com/1"},
            {"title": "Story 2", "summary": "Summary 2", "url": "https://example.com/2"},
        ]

        mock_scheduler = AsyncMock()
        mock_scheduler.enqueue.return_value = "task_abc123"

        with patch(
            "tldw_Server_API.app.core.Scheduler.get_global_scheduler",
            new_callable=AsyncMock,
            return_value=mock_scheduler,
        ):
            result = await trigger_audio_briefing(
                user_id=1,
                job_id=42,
                run_id=7,
                output_prefs={
                    "generate_audio": True,
                    "target_audio_minutes": 5,
                    "voice_map": {"HOST": "af_bella"},
                },
                db=db,
            )

        assert result == "task_abc123"
        mock_scheduler.enqueue.assert_called_once()

        # Verify the task payload
        task = mock_scheduler.enqueue.call_args[0][0]
        assert task.handler == "workflow_run"
        assert task.payload["user_id"] == 1
        assert task.payload["inputs"]["target_audio_minutes"] == 5
        assert task.payload["inputs"]["voice_map"] == {"HOST": "af_bella"}
        assert len(task.payload["inputs"]["items"]) == 2
        assert task.payload["metadata"]["watchlist_job_id"] == 42
        assert task.payload["metadata"]["watchlist_run_id"] == 7

    @pytest.mark.asyncio
    async def test_trigger_handles_scheduler_failure(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            trigger_audio_briefing,
        )

        db = MagicMock()
        db.list_scraped_items.return_value = [
            {"title": "Story", "summary": "S", "url": "https://x.com"},
        ]

        with patch(
            "tldw_Server_API.app.core.Scheduler.get_global_scheduler",
            new_callable=AsyncMock,
            side_effect=RuntimeError("scheduler not available"),
        ):
            result = await trigger_audio_briefing(
                user_id=1,
                job_id=1,
                run_id=1,
                output_prefs={"generate_audio": True},
                db=db,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_handles_db_error(self):
        from tldw_Server_API.app.core.Watchlists.audio_briefing_workflow import (
            trigger_audio_briefing,
        )

        db = MagicMock()
        db.list_scraped_items.side_effect = RuntimeError("db error")

        result = await trigger_audio_briefing(
            user_id=1,
            job_id=1,
            run_id=1,
            output_prefs={"generate_audio": True},
            db=db,
        )
        assert result is None
