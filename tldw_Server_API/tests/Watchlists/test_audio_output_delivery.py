"""Tests for audio output delivery endpoint.

Tests the GET /watchlists/runs/{run_id}/audio endpoint and
audio artifact lookup behavior.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestGetRunAudioEndpoint:
    """Tests for the /runs/{run_id}/audio endpoint."""

    @pytest.mark.asyncio
    async def test_returns_404_when_run_not_found(self):
        """Test 404 when run doesn't exist."""
        from tldw_Server_API.app.api.v1.endpoints.watchlists import get_run_audio

        db = MagicMock()
        db.get_run.side_effect = KeyError("not found")

        user = MagicMock()
        user.role = "admin"

        with pytest.raises(Exception) as exc_info:
            await get_run_audio(run_id=999, target_user_id=None, current_user=user, db=db)
        assert "404" in str(exc_info.value.status_code) or exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_no_audio_task(self):
        """Test 404 when run has no audio briefing task."""
        from tldw_Server_API.app.api.v1.endpoints.watchlists import get_run_audio

        run = SimpleNamespace(
            id=1, job_id=1, status="completed",
            started_at=None, finished_at=None,
            stats_json=json.dumps({"items_fetched": 10}),
            error_msg=None,
        )
        db = MagicMock()
        db.get_run.return_value = run

        user = MagicMock()
        user.role = "admin"

        with pytest.raises(Exception) as exc_info:
            await get_run_audio(run_id=1, target_user_id=None, current_user=user, db=db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_pending_when_workflow_not_found(self):
        """Test returns pending status when workflow run not found yet."""
        from tldw_Server_API.app.api.v1.endpoints.watchlists import get_run_audio

        run = SimpleNamespace(
            id=1, job_id=1, status="completed",
            started_at=None, finished_at=None,
            stats_json=json.dumps({"audio_briefing_task_id": "task_abc"}),
            error_msg=None,
        )
        db = MagicMock()
        db.get_run.return_value = run

        user = MagicMock()
        user.role = "admin"

        # Mock WorkflowsDB to return no matching runs
        mock_wf_db = MagicMock()
        mock_wf_db.list_runs.return_value = []

        with (
            patch(
                "tldw_Server_API.app.api.v1.endpoints.watchlists.resolve_user_id_for_request",
                return_value=1,
            ),
            patch(
                "tldw_Server_API.app.core.DB_Management.db_path_utils.DatabasePaths.get_user_base_directory",
                return_value="/tmp/test_user",
            ),
            patch("os.path.exists", return_value=True),
            patch(
                "tldw_Server_API.app.core.DB_Management.Workflows_DB.WorkflowsDatabase",
                return_value=mock_wf_db,
            ),
        ):
            result = await get_run_audio(run_id=1, target_user_id=None, current_user=user, db=db)

        assert result["status"] == "pending"
        assert result["task_id"] == "task_abc"
        assert result["audio_uri"] is None

    @pytest.mark.asyncio
    async def test_returns_audio_when_artifact_found(self):
        """Test returns audio info when artifact is found."""
        from tldw_Server_API.app.api.v1.endpoints.watchlists import get_run_audio

        run = SimpleNamespace(
            id=7, job_id=1, status="completed",
            started_at=None, finished_at=None,
            stats_json=json.dumps({"audio_briefing_task_id": "task_xyz"}),
            error_msg=None,
        )
        db = MagicMock()
        db.get_run.return_value = run

        user = MagicMock()
        user.role = "admin"

        # Mock workflow run with matching metadata
        wf_run = SimpleNamespace(
            id="wf_run_1",
            status="completed",
            metadata_json=json.dumps({"watchlist_run_id": 7}),
        )

        # Mock audio artifact
        audio_art = SimpleNamespace(
            id="art_audio_1",
            type="tts_audio",
            uri="file:///tmp/briefing.mp3",
            size_bytes=1024000,
            mime_type="audio/mpeg",
            metadata_json=json.dumps({"multi_voice": True}),
        )

        mock_wf_db = MagicMock()
        mock_wf_db.list_runs.return_value = [wf_run]
        mock_wf_db.list_artifacts.return_value = [audio_art]

        with (
            patch(
                "tldw_Server_API.app.api.v1.endpoints.watchlists.resolve_user_id_for_request",
                return_value=1,
            ),
            patch(
                "tldw_Server_API.app.core.DB_Management.db_path_utils.DatabasePaths.get_user_base_directory",
                return_value="/tmp/test_user",
            ),
            patch("os.path.exists", return_value=True),
            patch(
                "tldw_Server_API.app.core.DB_Management.Workflows_DB.WorkflowsDatabase",
                return_value=mock_wf_db,
            ),
        ):
            result = await get_run_audio(run_id=7, target_user_id=None, current_user=user, db=db)

        assert result["status"] == "completed"
        assert result["audio_uri"] == "file:///tmp/briefing.mp3"
        assert result["artifact_id"] == "art_audio_1"
        assert result["download_url"] == "/api/v1/workflows/artifacts/art_audio_1/download"
        assert result["size_bytes"] == 1024000

    @pytest.mark.asyncio
    async def test_handles_db_errors_gracefully(self):
        """Test graceful error handling when workflow DB lookup fails."""
        from tldw_Server_API.app.api.v1.endpoints.watchlists import get_run_audio

        run = SimpleNamespace(
            id=1, job_id=1, status="completed",
            started_at=None, finished_at=None,
            stats_json=json.dumps({"audio_briefing_task_id": "task_fail"}),
            error_msg=None,
        )
        db = MagicMock()
        db.get_run.return_value = run

        user = MagicMock()
        user.role = "admin"

        with (
            patch(
                "tldw_Server_API.app.api.v1.endpoints.watchlists.resolve_user_id_for_request",
                return_value=1,
            ),
            patch(
                "tldw_Server_API.app.core.DB_Management.db_path_utils.DatabasePaths.get_user_base_directory",
                side_effect=RuntimeError("db path error"),
            ),
        ):
            result = await get_run_audio(run_id=1, target_user_id=None, current_user=user, db=db)

        assert result["status"] == "unknown"
        assert result["task_id"] == "task_fail"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_paginated_scan_returns_pending_when_no_matching_run(self):
        """Scans beyond first page and returns pending when no metadata match exists."""
        from tldw_Server_API.app.api.v1.endpoints.watchlists import get_run_audio

        run = SimpleNamespace(
            id=77, job_id=1, status="completed",
            started_at=None, finished_at=None,
            stats_json=json.dumps({"audio_briefing_task_id": "task_paged_pending"}),
            error_msg=None,
        )
        db = MagicMock()
        db.get_run.return_value = run

        user = MagicMock()
        user.role = "admin"
        user.id = 1
        user.tenant_id = "default"

        page1 = [
            SimpleNamespace(
                run_id=f"wf_{idx}",
                status="running",
                metadata_json=json.dumps({"watchlist_run_id": 99999}),
            )
            for idx in range(50)
        ]
        page2 = [
            SimpleNamespace(
                run_id=f"wf_tail_{idx}",
                status="running",
                metadata_json=json.dumps({"watchlist_run_id": 88888}),
            )
            for idx in range(25)
        ]

        mock_wf_db = MagicMock()
        mock_wf_db.list_runs.side_effect = [page1, page2]

        with (
            patch(
                "tldw_Server_API.app.api.v1.endpoints.watchlists.resolve_user_id_for_request",
                return_value=1,
            ),
            patch(
                "tldw_Server_API.app.core.DB_Management.db_path_utils.DatabasePaths.get_user_base_directory",
                return_value="/tmp/test_user",
            ),
            patch("os.path.exists", return_value=True),
            patch(
                "tldw_Server_API.app.core.DB_Management.Workflows_DB.WorkflowsDatabase",
                return_value=mock_wf_db,
            ),
        ):
            result = await get_run_audio(run_id=77, target_user_id=None, current_user=user, db=db)

        assert result["status"] == "pending"
        assert result["task_id"] == "task_paged_pending"
        assert mock_wf_db.list_runs.call_count == 2
        first_call = mock_wf_db.list_runs.call_args_list[0].kwargs
        second_call = mock_wf_db.list_runs.call_args_list[1].kwargs
        assert first_call["offset"] == 0
        assert second_call["offset"] == 50

    @pytest.mark.asyncio
    async def test_paginated_scan_finds_matching_run_and_audio_later_page(self):
        """Finds match after first page and returns artifact metadata."""
        from tldw_Server_API.app.api.v1.endpoints.watchlists import get_run_audio

        run = SimpleNamespace(
            id=42, job_id=1, status="completed",
            started_at=None, finished_at=None,
            stats_json=json.dumps({"audio_briefing_task_id": "task_paged_hit"}),
            error_msg=None,
        )
        db = MagicMock()
        db.get_run.return_value = run

        user = MagicMock()
        user.role = "admin"
        user.id = 1
        user.tenant_id = "default"

        page1 = [
            SimpleNamespace(
                run_id=f"wf_old_{idx}",
                status="completed",
                metadata_json=json.dumps({"watchlist_run_id": 123456}),
            )
            for idx in range(50)
        ]
        matching_run = SimpleNamespace(
            run_id="wf_target_42",
            status="completed",
            metadata_json=json.dumps({"watchlist_run_id": 42}),
        )
        page2 = [matching_run]

        audio_art = SimpleNamespace(
            id="art_audio_paged",
            type="tts_audio",
            uri="file:///tmp/paged-briefing.mp3",
            size_bytes=777,
            mime_type="audio/mpeg",
            metadata_json=json.dumps({"multi_voice": True}),
        )

        mock_wf_db = MagicMock()
        mock_wf_db.list_runs.side_effect = [page1, page2]
        mock_wf_db.list_artifacts.return_value = [audio_art]

        with (
            patch(
                "tldw_Server_API.app.api.v1.endpoints.watchlists.resolve_user_id_for_request",
                return_value=1,
            ),
            patch(
                "tldw_Server_API.app.core.DB_Management.db_path_utils.DatabasePaths.get_user_base_directory",
                return_value="/tmp/test_user",
            ),
            patch("os.path.exists", return_value=True),
            patch(
                "tldw_Server_API.app.core.DB_Management.Workflows_DB.WorkflowsDatabase",
                return_value=mock_wf_db,
            ),
        ):
            result = await get_run_audio(run_id=42, target_user_id=None, current_user=user, db=db)

        assert result["status"] == "completed"
        assert result["task_id"] == "task_paged_hit"
        assert result["artifact_id"] == "art_audio_paged"
        assert result["audio_uri"] == "file:///tmp/paged-briefing.mp3"
        assert mock_wf_db.list_runs.call_count == 2
        first_call = mock_wf_db.list_runs.call_args_list[0].kwargs
        second_call = mock_wf_db.list_runs.call_args_list[1].kwargs
        assert first_call["offset"] == 0
        assert second_call["offset"] == 50

    @pytest.mark.asyncio
    async def test_prefers_final_or_mixed_artifact_when_multiple_candidates(self):
        """Returns final-tagged/mixed artifact over earlier intermediate artifacts."""
        from tldw_Server_API.app.api.v1.endpoints.watchlists import get_run_audio

        run = SimpleNamespace(
            id=88,
            job_id=1,
            status="completed",
            started_at=None,
            finished_at=None,
            stats_json=json.dumps({"audio_briefing_task_id": "task_prefer_final"}),
            error_msg=None,
        )
        db = MagicMock()
        db.get_run.return_value = run

        user = MagicMock()
        user.role = "admin"
        user.id = 1
        user.tenant_id = "default"

        wf_run = SimpleNamespace(
            run_id="wf_run_88",
            status="completed",
            metadata_json=json.dumps({"watchlist_run_id": 88}),
        )
        intermediate = SimpleNamespace(
            id="art_raw",
            type="tts_audio",
            uri="file:///tmp/briefing_raw.mp3",
            size_bytes=120,
            mime_type="audio/mpeg",
            metadata_json=json.dumps({"multi_voice": True}),
        )
        final_mixed = SimpleNamespace(
            id="art_final",
            type="tts_audio",
            uri="file:///tmp/briefing_mixed.mp3",
            size_bytes=240,
            mime_type="audio/mpeg",
            metadata_json=json.dumps(
                {
                    "multi_voice": True,
                    "background_mixed": True,
                    "final_artifact": True,
                }
            ),
        )

        mock_wf_db = MagicMock()
        mock_wf_db.list_runs.return_value = [wf_run]
        mock_wf_db.list_artifacts.return_value = [intermediate, final_mixed]

        with (
            patch(
                "tldw_Server_API.app.api.v1.endpoints.watchlists.resolve_user_id_for_request",
                return_value=1,
            ),
            patch(
                "tldw_Server_API.app.core.DB_Management.db_path_utils.DatabasePaths.get_user_base_directory",
                return_value="/tmp/test_user",
            ),
            patch("os.path.exists", return_value=True),
            patch(
                "tldw_Server_API.app.core.DB_Management.Workflows_DB.WorkflowsDatabase",
                return_value=mock_wf_db,
            ),
        ):
            result = await get_run_audio(run_id=88, target_user_id=None, current_user=user, db=db)

        assert result["status"] == "completed"
        assert result["artifact_id"] == "art_final"
        assert result["audio_uri"] == "file:///tmp/briefing_mixed.mp3"
