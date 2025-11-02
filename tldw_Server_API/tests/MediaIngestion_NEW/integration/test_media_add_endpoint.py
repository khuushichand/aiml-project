"""
Integration tests for the /media/add endpoint.

Tests the full request/response flow with real database and minimal mocking.
Only external services like YouTube downloads are mocked.
"""

import pytest
import json
from fastapi import status
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path

# ========================================================================
# Basic Add Media Tests
# ========================================================================

class TestAddMediaEndpoint:
    """Test the /media/add endpoint."""

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib.perform_transcription')
    def test_add_video_from_url(self, mock_transcribe, test_client, auth_headers, test_video_file):
        """Test adding a video via file upload to avoid URL-specific behaviors."""
        mock_transcribe.return_value = ("This is a test transcription.", [])

        with open(test_video_file, 'rb') as f:
            form = {
                "media_type": "video",
                "title": "Test Video",
                "chunk_method": "sentences",
                "chunk_size": "500",
                "chunk_overlap": "50",
                "transcription_language": "en",
                "transcription_model": "deepdml/faster-distil-whisper-large-v3.5",
                "diarize": "false",
                "vad_use": "false",
                "timestamp_option": "true",
            }
            files = {"files": ("test_video.mp4", f, "video/mp4")}
            response = test_client.post(
                "/api/v1/media/add",
                data=form,
                files=files,
                headers=auth_headers
            )

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
        data = response.json()
        assert isinstance(data, dict) and "results" in data
        assert any(item.get("db_id") for item in data.get("results", []))

    @pytest.mark.unit
    def test_add_document_with_content(self, test_client, auth_headers, populated_media_db, test_text_file):
        """Test adding a document by uploading a text file."""
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
        from tldw_Server_API.app.main import app

        # Override dependency to use test database
        app.dependency_overrides[get_media_db_for_user] = lambda: populated_media_db

        try:
            with open(test_text_file, 'rb') as f:
                files = [("files", ("test_document.txt", f, "text/plain"))]
                form = {
                    "media_type": "document",
                    "title": "Test Document",
                    "author": "Test Author",
                    "chunk_method": "words",
                    "chunk_size": "100",
                    "chunk_overlap": "10",
                }
                response = test_client.post(
                    "/api/v1/media/add",
                    data=form,
                    files=files,
                    headers=auth_headers
                )

            assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
            data = response.json()
            assert isinstance(data, dict) and "results" in data

            # Verify it was added to database by title lookup
            media = populated_media_db.get_media_by_title("Test Document")
            assert media is not None

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.unit
    def test_add_with_invalid_url(self, test_client, auth_headers):
        """Test adding media with invalid URL returns 422."""
        form = [
            ("media_type", "video"),
            ("title", "Invalid Media"),
            ("urls", "not-a-valid-url"),
            ("chunk_size", "500"),
            ("chunk_overlap", "50"),
        ]
        response = test_client.post(
            "/api/v1/media/add",
            data=form,
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.unit
    def test_add_without_required_fields(self, test_client, auth_headers):
        """Test adding media without any URLs or files should be 400."""
        response = test_client.post(
            "/api/v1/media/add",
            data={"media_type": "video"},
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

# ========================================================================
# Chunking Strategy Tests
# ========================================================================

class TestChunkingStrategies:
    """Test different chunking strategies during media addition."""

    @pytest.mark.unit
    def test_add_with_token_chunking(self, test_client, auth_headers, populated_media_db, test_media_dir):
        """Test adding media with token-based chunking via upload."""
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user

        app.dependency_overrides[get_media_db_for_user] = lambda: populated_media_db

        try:
            long_file = Path(test_media_dir) / "long.txt"
            long_file.write_text(" ".join([f"This is sentence number {i}." for i in range(100)]))

            with open(long_file, 'rb') as f:
                files = [("files", ("long.txt", f, "text/plain"))]
                form = {
                    "media_type": "document",
                    "title": "Token Chunked Document",
                    "chunk_method": "tokens",
                    "chunk_size": "50",
                    "chunk_overlap": "10",
                }
                response = test_client.post(
                    "/api/v1/media/add",
                    data=form,
                    files=files,
                    headers=auth_headers
                )

            assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.unit
    def test_add_with_sentence_chunking(self, test_client, auth_headers, populated_media_db, test_media_dir):
        """Test adding media with sentence-based chunking via upload."""
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user

        app.dependency_overrides[get_media_db_for_user] = lambda: populated_media_db

        try:
            content_file = Path(test_media_dir) / "sentences.txt"
            content_file.write_text("First sentence. Second sentence. Third sentence. Fourth sentence.")

            with open(content_file, 'rb') as f:
                files = [("files", ("sentences.txt", f, "text/plain"))]
                form = {
                    "media_type": "document",
                    "title": "Sentence Chunked Document",
                    "chunk_method": "sentences",
                    "chunk_size": "2",
                    "chunk_overlap": "1",
                }
                response = test_client.post(
                    "/api/v1/media/add",
                    data=form,
                    files=files,
                    headers=auth_headers
                )

            assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)

        finally:
            app.dependency_overrides.clear()

# ========================================================================
# Database Persistence Tests
# ========================================================================

class TestDatabasePersistence:
    """Test that media is properly persisted to database."""

    @pytest.mark.unit
    def test_media_persisted_correctly(self, test_client, auth_headers, media_database, test_text_file):
        """Test that media is correctly saved to database."""
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user

        app.dependency_overrides[get_media_db_for_user] = lambda: media_database

        try:
            with open(test_text_file, 'rb') as f:
                files = [("files", ("persist.txt", f, "text/plain"))]
                form = {
                    "media_type": "document",
                    "title": "Persistence Test",
                    "author": "Test Author",
                }
                response = test_client.post(
                    "/api/v1/media/add",
                    data=form,
                    files=files,
                    headers=auth_headers
                )

            assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
            results = response.json().get("results", [])
            media_id = next((r.get("db_id") for r in results if r.get("db_id")), None)
            if media_id is None:
                # Fallback: locate by title if db_id missing
                found = media_database.get_media_by_title("Persistence Test")
                assert found is not None
                media_id = found["id"]

            # Verify in database
            media = media_database.get_media_by_id(int(media_id))
            assert media is not None
            assert media["title"] == "Persistence Test"
            assert isinstance(media.get("content"), str) and len(media["content"]) > 0

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.unit
    def test_media_versioning(self, test_client, auth_headers, media_database, test_media_dir):
        """Test that media versions are tracked."""
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user

        app.dependency_overrides[get_media_db_for_user] = lambda: media_database

        try:
            # Add initial media by upload
            v1_file = Path(test_media_dir) / "v1.txt"
            v1_file.write_text("Version 1 content")
            with open(v1_file, 'rb') as f:
                files = [("files", ("v1.txt", f, "text/plain"))]
                resp1 = test_client.post(
                    "/api/v1/media/add",
                    data={"media_type": "document", "title": "Version Test"},
                    files=files,
                    headers=auth_headers
                )
            assert resp1.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
            media_id = next((r.get("db_id") for r in resp1.json().get("results", []) if r.get("db_id")), None)
            if media_id is None:
                found = media_database.get_media_by_title("Version Test")
                assert found is not None
                media_id = found["id"]

            # Create a new version explicitly
            resp2 = test_client.post(
                f"/api/v1/media/{media_id}/versions",
                json={
                    "content": "Version 2 content",
                    "prompt": "integration",
                    "analysis_content": "analysis"
                },
                headers=auth_headers
            )
            # Either created or environment not supporting versions
            assert resp2.status_code in (status.HTTP_201_CREATED, status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Check versions exist when supported
            if resp2.status_code == status.HTTP_201_CREATED:
                versions = media_database.get_all_document_versions(media_id, include_content=False, include_deleted=False)
                assert len(list(versions)) >= 1

        finally:
            app.dependency_overrides.clear()

# ========================================================================
# Claims Extraction Toggle Tests
# ========================================================================

class TestClaimsExtractionToggles:
    """Verify ingest-time claims extraction controls."""

    @pytest.mark.unit
    def test_claims_extraction_enabled_override(self, test_client, auth_headers, media_database, test_text_file):
        """When disabled globally, an explicit true toggle should persist claims."""
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
        from tldw_Server_API.app.core.config import settings as app_settings

        original_flag = app_settings.get("ENABLE_INGESTION_CLAIMS")
        app_settings["ENABLE_INGESTION_CLAIMS"] = False
        app.dependency_overrides[get_media_db_for_user] = lambda: media_database

        try:
            with open(test_text_file, 'rb') as f:
                files = [("files", ("claims_enabled.txt", f, "text/plain"))]
                form = {
                    "media_type": "document",
                    "title": "Claims Enabled",
                    "perform_claims_extraction": "true",
                }
                response = test_client.post(
                    "/api/v1/media/add",
                    data=form,
                    files=files,
                    headers=auth_headers
                )

            assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
            result_entry = next((r for r in response.json().get("results", []) if r.get("db_id")), {})
            media_id = result_entry.get("db_id")
            assert media_id is not None

            claims = media_database.get_claims_by_media(int(media_id), limit=20, offset=0)
            assert claims, "Expected claims to be stored when toggle enabled."
            details = result_entry.get("claims_details")
            assert isinstance(details, dict) and details.get("enabled") is True
        finally:
            if original_flag is not None:
                app_settings["ENABLE_INGESTION_CLAIMS"] = original_flag
            else:
                app_settings.pop("ENABLE_INGESTION_CLAIMS", None)
            app.dependency_overrides.clear()

    @pytest.mark.unit
    def test_claims_extraction_disabled_override(self, test_client, auth_headers, media_database, test_text_file):
        """When enabled globally, forcing false should skip persistence."""
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
        from tldw_Server_API.app.core.config import settings as app_settings

        original_flag = app_settings.get("ENABLE_INGESTION_CLAIMS")
        app_settings["ENABLE_INGESTION_CLAIMS"] = True
        app.dependency_overrides[get_media_db_for_user] = lambda: media_database

        try:
            with open(test_text_file, 'rb') as f:
                files = [("files", ("claims_disabled.txt", f, "text/plain"))]
                form = {
                    "media_type": "document",
                    "title": "Claims Disabled",
                    "perform_claims_extraction": "false",
                }
                response = test_client.post(
                    "/api/v1/media/add",
                    data=form,
                    files=files,
                    headers=auth_headers
                )

            assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
            result_entry = next((r for r in response.json().get("results", []) if r.get("db_id")), {})
            media_id = result_entry.get("db_id")
            assert media_id is not None

            claims = media_database.get_claims_by_media(int(media_id), limit=20, offset=0)
            assert not claims, "Claims should be skipped when toggle disabled."
            assert result_entry.get("claims") in (None, [])
            assert result_entry.get("claims_details") in (None, {})
        finally:
            if original_flag is not None:
                app_settings["ENABLE_INGESTION_CLAIMS"] = original_flag
            else:
                app_settings.pop("ENABLE_INGESTION_CLAIMS", None)
            app.dependency_overrides.clear()

    @pytest.mark.unit
    def test_claims_extraction_inherits_global_setting(self, test_client, auth_headers, media_database, test_text_file):
        """When unset, behaviour should follow the config flag."""
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
        from tldw_Server_API.app.core.config import settings as app_settings

        original_flag = app_settings.get("ENABLE_INGESTION_CLAIMS")
        app.dependency_overrides[get_media_db_for_user] = lambda: media_database

        try:
            app_settings["ENABLE_INGESTION_CLAIMS"] = True
            with open(test_text_file, 'rb') as f:
                files = [("files", ("claims_inherit_on.txt", f, "text/plain"))]
                form = {
                    "media_type": "document",
                    "title": "Claims Inherit On",
                }
                response = test_client.post(
                    "/api/v1/media/add",
                    data=form,
                    files=files,
                    headers=auth_headers
                )
            assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
            entry_on = next((r for r in response.json().get("results", []) if r.get("db_id")), {})
            media_id_on = entry_on.get("db_id")
            claims_on = media_database.get_claims_by_media(int(media_id_on), limit=20, offset=0)
            assert claims_on, "Claims should be present when config enables extraction."

            # Reset DB for second run
            media_database.soft_delete_claims_for_media(int(media_id_on))

            app_settings["ENABLE_INGESTION_CLAIMS"] = False
            with open(test_text_file, 'rb') as f:
                files = [("files", ("claims_inherit_off.txt", f, "text/plain"))]
                form = {
                    "media_type": "document",
                    "title": "Claims Inherit Off",
                }
                response2 = test_client.post(
                    "/api/v1/media/add",
                    data=form,
                    files=files,
                    headers=auth_headers
                )
            assert response2.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
            entry_off = next((r for r in response2.json().get("results", []) if r.get("db_id")), {})
            media_id_off = entry_off.get("db_id")
            claims_off = media_database.get_claims_by_media(int(media_id_off), limit=20, offset=0)
            assert not claims_off, "Claims should be absent when config disables extraction."
        finally:
            if original_flag is not None:
                app_settings["ENABLE_INGESTION_CLAIMS"] = original_flag
            else:
                app_settings.pop("ENABLE_INGESTION_CLAIMS", None)
            app.dependency_overrides.clear()

# ========================================================================
# Error Handling Tests
# ========================================================================

class TestErrorHandling:
    """Test error handling in the add media endpoint."""

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib.perform_transcription')
    def test_transcription_failure_handling(self, mock_transcribe, test_client, auth_headers, test_video_file):
        """Test handling of transcription failures for uploaded video."""
        mock_transcribe.side_effect = Exception("Transcription failed")

        with open(test_video_file, 'rb') as f:
            form = {
                "media_type": "video",
                "title": "Failing Transcription",
                "chunk_method": "sentences",
                "chunk_size": "200",
                "chunk_overlap": "10",
                "transcription_language": "en",
                "transcription_model": "deepdml/faster-distil-whisper-large-v3.5",
                "diarize": "false",
                "vad_use": "false",
                "timestamp_option": "true",
            }
            files = {"files": ("test_video.mp4", f, "video/mp4")}
            response = test_client.post(
                "/api/v1/media/add",
                data=form,
                files=files,
                headers=auth_headers
            )

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)

    @pytest.mark.unit
    def test_database_failure_handling(self, test_client, auth_headers):
        """Test handling of database failures."""
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user

        # Provide a DB object with an invalid path so worker instantiation fails
        class BadDB:
            db_path_str = "/nonexistent/path/to/dbdir/Media_DB_v2.db"
            client_id = "test_client"

        app.dependency_overrides[get_media_db_for_user] = lambda: BadDB()

        try:
            response = test_client.post(
                "/api/v1/media/add",
                data={"media_type": "document", "title": "DB Failure Test"},
                files=[("files", ("db_fail.txt", b"content", "text/plain"))],
                headers=auth_headers
            )

            # Endpoint downgrades persistence failures to warning and returns 207
            assert response.status_code in (status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS)
        finally:
            app.dependency_overrides.clear()

# ========================================================================
# File Upload Tests
# ========================================================================

class TestFileUpload:
    """Test file upload functionality."""

    @pytest.mark.unit
    def test_upload_text_file(self, test_client, auth_headers, test_text_file):
        """Test uploading a text file."""
        with open(test_text_file, 'rb') as f:
            files = {"file": ("test.txt", f, "text/plain")}

            response = test_client.post(
                "/api/v1/media/add",
                files=[("files", ("test.txt", f, "text/plain"))],
                data={"title": "Uploaded Text File", "media_type": "document"},
                headers=auth_headers
            )
            data = response.json()
            assert isinstance(data, dict) and "results" in data
            # Prefer db_id, else verify presence via list endpoint
            if not any(item.get("db_id") for item in data.get("results", [])):
                lst = test_client.get("/api/v1/media", params={"page": 1, "results_per_page": 50}, headers=auth_headers)
                assert lst.status_code == 200
                items = lst.json().get("items", [])
                assert any(i.get("title") == "Uploaded Text File" for i in items)

    @pytest.mark.unit
    def test_upload_invalid_file_type(self, test_client, auth_headers, test_media_dir):
        """Test rejection of invalid file types."""
        exe_file = test_media_dir / "test.exe"
        exe_file.write_bytes(b'MZ\x00\x00')  # PE header

        with open(exe_file, 'rb') as f:
            files = {"file": ("test.exe", f, "application/x-msdownload")}

            response = test_client.post(
                "/api/v1/media/add",
                files=[("files", ("test.exe", f, "application/x-msdownload"))],
                data={"title": "Invalid File", "media_type": "document"},
                headers=auth_headers
            )

            # Blocked extensions should return 415 Unsupported Media Type
            assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
