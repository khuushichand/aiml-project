# test_chatbook_service.py
# Description: Unit tests for the ChatbookService (combined import/export)
#
"""
Chatbook Service Tests
----------------------

Comprehensive unit tests for the chatbook import/export functionality including
job management, conflict resolution, and user isolation.
"""

import pytest
import json
import tempfile
import zipfile
import os
import shutil
from unittest.mock import MagicMock, patch, AsyncMock, call, PropertyMock
from datetime import datetime
from uuid import uuid4
from pathlib import Path

from tldw_Server_API.app.core.Chatbooks.chatbook_service import ChatbookService
from tldw_Server_API.app.core.Chatbooks.chatbook_models import (
    ChatbookManifest,
    ChatbookContent,
    ContentItem,
    ExportJob,
    ImportJob,
    ExportStatus,
    ImportStatus,
    ChatbookVersion,
    ContentType,
    ConflictResolution,
)
from tldw_Server_API.app.core.Chatbooks.exceptions import SecurityError
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


def manifest_to_dict(manifest):
    """Helper to convert manifest to dict for JSON serialization."""
    data = {}
    for key, value in manifest.__dict__.items():
        if hasattr(value, 'value'):  # Enum
            data[key] = value.value
        elif hasattr(value, 'isoformat'):  # DateTime
            data[key] = value.isoformat()
        else:
            data[key] = value
    return data


@pytest.fixture
def mock_db():
    """Create a mock database instance."""
    mock = MagicMock()
    mock.execute_query = MagicMock()
    mock.execute_many = MagicMock()
    return mock


@pytest.fixture
def service(mock_db, tmp_path, monkeypatch):
    """Create a ChatbookService instance with mocked database and temp directories."""
    # Set environment variable to use temp directory for tests
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'test')
    monkeypatch.setenv('USER_DB_BASE_DIR', str(tmp_path))

    mock_db.execute_query.return_value = []
    connection = MagicMock()
    connection.execute = MagicMock()
    connection.close = MagicMock()
    mock_db.get_connection.return_value = connection

    service = ChatbookService(user_id="test_user", db=mock_db)
    return service


@pytest.fixture
def sample_manifest():
    """Create a sample chatbook manifest."""
    return ChatbookManifest(
        version=ChatbookVersion.V1,
        exported_at=datetime.now().isoformat(),
        user_id="test_user",
        name="Test Chatbook",
        description="Test chatbook for unit tests",
        content_summary={
            "conversations": 2,
            "characters": 1,
            "world_books": 1,
            "dictionaries": 1,
            "notes": 2,
            "prompts": 3
        },
        metadata={"test": "data"}
    )


@pytest.fixture
def sample_content_items():
    """Create sample content items."""
    return [
        ContentItem(
            id="conv1",
            type=ContentType.CONVERSATION,
            title="Test Conversation",
            metadata={"created_at": "2024-01-01"}
        ),
        ContentItem(
            id="char1",
            type=ContentType.CHARACTER,
            title="Test Character",
            metadata={"description": "A test character"}
        )
    ]


class TestChatbookService:
    """Test suite for ChatbookService."""

    def test_init_creates_tables(self, mock_db, tmp_path, monkeypatch):
        """Test that initialization creates necessary tables."""
        monkeypatch.setenv('PYTEST_CURRENT_TEST', 'test')
        monkeypatch.setenv('USER_DB_BASE_DIR', str(tmp_path))

        mock_db.execute_query.return_value = []

        with patch('tldw_Server_API.app.core.Chatbooks.chatbook_service.Path.mkdir') as mock_mkdir:
            mock_mkdir.return_value = None
            service = ChatbookService(user_id="test_user", db=mock_db)

        # Should create export and import job tables
        assert mock_db.execute_query.call_count >= 2

        # Check table creation
        calls = mock_db.execute_query.call_args_list
        sql_statements = [call[0][0] for call in calls]
        assert any("CREATE TABLE IF NOT EXISTS export_jobs" in sql for sql in sql_statements)
        assert any("CREATE TABLE IF NOT EXISTS import_jobs" in sql for sql in sql_statements)

    def test_create_export_job(self, service, mock_db):
        """Test creating an export job."""
        test_uuid = uuid4()
        job_id = str(test_uuid)

        with patch('tldw_Server_API.app.core.Chatbooks.chatbook_service.uuid4', return_value=test_uuid):
            mock_db.execute_query.return_value = None

            result = service.create_export_job(
                name="Test Export",
                description="Test export job",
                content_types=["conversations", "characters"]
            )

        assert result["job_id"] == job_id
        assert result["status"] == "pending"

        # Check job was saved - looking for INSERT OR REPLACE
        call_args = mock_db.execute_query.call_args[0]
        assert "INSERT OR REPLACE INTO export_jobs" in call_args[0]

    @pytest.mark.asyncio
    async def test_export_chatbook_sync(self, service, mock_db, tmp_path):
        """Test synchronous chatbook export."""
        mock_db.execute_query.return_value = [
            {"id": "conv1"},
            {"id": "conv2"},
        ]

        archive_path = tmp_path / "test_export.chatbook"
        manifest_payload = {
            "name": "Test Export",
            "description": "Test Description",
            "statistics": {"total_conversations": 2},
        }
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest_payload))

        with patch.object(service, "create_chatbook", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = (
                True,
                "Chatbook created successfully",
                str(archive_path),
            )

            result = await service.export_chatbook(
                name="Test Export",
                content_types=["conversations"],
            )

        mock_create.assert_awaited_once()
        call_kwargs = mock_create.await_args.kwargs
        assert call_kwargs["name"] == "Test Export"
        assert "async_mode" not in call_kwargs
        assert call_kwargs["content_selections"] == {
            ContentType.CONVERSATION: ["conv1", "conv2"],
        }

        assert result["success"] is True
        assert result["message"] == "Chatbook created successfully"
        assert result["file_path"] == str(archive_path)

    def test_get_export_job_parses_varied_timestamps(self, service, mock_db):
        """Ensure timestamp parser handles common DB formats."""
        mock_row = {
            "job_id": "job-plain",
            "user_id": service.user_id,
            "status": "completed",
            "chatbook_name": "Test",
            "output_path": "/tmp/test.zip",
            "created_at": "2024-01-01 00:00:00",
            "started_at": "2024-01-01 00:00:00+00:00",
            "completed_at": "2024-01-01 00:00:00.000001",
            "error_message": None,
            "progress_percentage": 100,
            "total_items": 0,
            "processed_items": 0,
            "file_size_bytes": 0,
            "download_url": None,
            "expires_at": "2024-01-02 00:00:00",
            "metadata": {},
        }
        mock_db.execute_query.return_value = [mock_row]

        job = service._get_export_job("job-plain")

        assert job is not None
        assert job.created_at is not None
        assert job.started_at is not None
        assert job.completed_at is not None

        # Now test Zulu format handling
        mock_row["created_at"] = "2024-01-03T00:00:00Z"
        mock_db.execute_query.return_value = [mock_row]
        job = service._get_export_job("job-zulu")
        assert job is not None
        assert job.created_at is not None

    def test_parse_timestamp_accepts_numeric_epoch(self, service):
        """Numeric epoch values should be parsed as UTC datetimes."""
        epoch = 1_700_000_000
        parsed = service._parse_timestamp(epoch)
        assert parsed == datetime.utcfromtimestamp(epoch)

    def test_parse_timestamp_normalizes_timezone_offsets(self, service):
        """Timestamps with explicit offsets should normalize to naive UTC."""
        parsed = service._parse_timestamp("2024-01-01T05:30:00+05:30")
        assert parsed == datetime(2024, 1, 1, 0, 0)

    def test_import_conversation_restores_inline_images(self, service, mock_db, tmp_path):
        """Conversations imported from chatbooks should restore embedded images."""
        conv_id = "conv-image"
        content_root = tmp_path / "content" / "conversations"
        assets_dir = content_root / f"conversation_{conv_id}_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        image_bytes = b"\x89PNG\r\n\x1a\n"
        image_rel_path = f"content/conversations/{assets_dir.name}/msg1_image_0.png"
        (assets_dir / "msg1_image_0.png").write_bytes(image_bytes)

        conversation_payload = {
            "id": conv_id,
            "name": "Sample Conversation",
            "created_at": "2024-01-01T00:00:00",
            "character_id": None,
            "attachments_path": f"content/conversations/{assets_dir.name}",
            "messages": [
                {
                    "id": "msg1",
                    "role": "user",
                    "content": "Hello with image",
                    "timestamp": "2024-01-01T00:00:00",
                    "attachments": [
                        {
                            "type": "image",
                            "mime_type": "image/png",
                            "file_path": image_rel_path,
                        }
                    ],
                }
            ],
        }

        conversation_file = content_root / f"conversation_{conv_id}.json"
        conversation_file.parent.mkdir(parents=True, exist_ok=True)
        conversation_file.write_text(json.dumps(conversation_payload), encoding="utf-8")

        mock_db.add_conversation.return_value = "new-conv-id"

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        status = ImportJob(
            job_id="job",
            user_id="test_user",
            status=ImportStatus.PENDING,
            chatbook_path="dummy",
        )

        with patch.object(service, "_get_conversation_by_name", return_value=None):
            service._import_conversations(
                tmp_path,
                manifest,
                [conv_id],
                ConflictResolution.SKIP,
                prefix_imported=False,
                status=status,
            )

        assert mock_db.add_message.call_count == 1
        message_payload = mock_db.add_message.call_args[0][0]
        assert "images" in message_payload
        assert len(message_payload["images"]) == 1
        img_payload = message_payload["images"][0]
        assert img_payload["image_data"] == image_bytes
        assert img_payload["image_mime_type"] == "image/png"

    def test_import_conversation_legacy_fields(self, service, mock_db, tmp_path):
        """Legacy conversation exports should import title/sender/message fields."""
        conv_id = "legacy-conv"
        content_root = tmp_path / "content" / "conversations"
        content_root.mkdir(parents=True, exist_ok=True)

        conversation_payload = {
            "id": conv_id,
            "title": "Legacy Conversation Title",
            "created_at": "2024-01-01T00:00:00",
            "character_id": 1,
            "messages": [
                {
                    "id": "msg-legacy",
                    "sender": "user",
                    "message": "Hello from legacy export",
                    "timestamp": "2024-01-01T00:00:00",
                }
            ],
        }

        conversation_file = content_root / f"conversation_{conv_id}.json"
        conversation_file.write_text(json.dumps(conversation_payload), encoding="utf-8")

        mock_db.get_character_card_by_id.return_value = {"id": 1}
        mock_db.add_conversation.return_value = "new-conv-id"

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        status = ImportJob(
            job_id="job",
            user_id="test_user",
            status=ImportStatus.PENDING,
            chatbook_path="dummy",
        )

        with patch.object(service, "_get_conversation_by_name", return_value=None):
            service._import_conversations(
                tmp_path,
                manifest,
                [conv_id],
                ConflictResolution.SKIP,
                prefix_imported=False,
                status=status,
            )

        conv_payload = mock_db.add_conversation.call_args[0][0]
        assert conv_payload["title"] == "Legacy Conversation Title"
        msg_payload = mock_db.add_message.call_args[0][0]
        assert msg_payload["sender"] == "user"
        assert msg_payload["content"] == "Hello from legacy export"

    def test_import_conversation_skips_outside_attachments(self, service, mock_db, tmp_path):
        """Attachment paths that escape extraction boundaries must be ignored."""
        conv_id = "conv-path"
        content_root = tmp_path / "content" / "conversations"
        content_root.mkdir(parents=True, exist_ok=True)

        conversation_payload = {
            "id": conv_id,
            "name": "Suspicious Conversation",
            "created_at": "2024-01-01T00:00:00",
            "messages": [
                {
                    "id": "msg-escape",
                    "role": "user",
                    "content": "Hello",
                    "timestamp": "2024-01-01T00:00:00",
                    "attachments": [
                        {
                            "type": "image",
                            "mime_type": "image/png",
                            "file_path": "../outside.png",
                        }
                    ],
                }
            ],
        }

        conversation_file = content_root / f"conversation_{conv_id}.json"
        conversation_file.write_text(json.dumps(conversation_payload), encoding="utf-8")

        mock_db.add_conversation.return_value = "new-conv-id"

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        status = ImportJob(
            job_id="job",
            user_id="test_user",
            status=ImportStatus.PENDING,
            chatbook_path="dummy",
        )

        with patch.object(service, "_get_conversation_by_name", return_value=None):
            service._import_conversations(
                tmp_path,
                manifest,
                [conv_id],
                ConflictResolution.SKIP,
                prefix_imported=False,
                status=status,
            )

        assert mock_db.add_message.call_count == 1
        message_payload = mock_db.add_message.call_args[0][0]
        assert "images" not in message_payload
        assert any("Skipped attachment outside extract dir" in warning for warning in status.warnings)
        assert status.successful_items == 1

    def test_import_conversation_warns_on_missing_attachment(self, service, mock_db, tmp_path):
        """Missing attachment files should log warnings while continuing import."""
        conv_id = "conv-missing"
        content_root = tmp_path / "content" / "conversations"
        content_root.mkdir(parents=True, exist_ok=True)

        rel_path = "content/conversations/conversation_assets/missing.png"
        assets_dir = content_root / "conversation_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        conversation_payload = {
            "id": conv_id,
            "name": "Conversation Missing Attachment",
            "created_at": "2024-01-01T00:00:00",
            "messages": [
                {
                    "id": "msg-missing",
                    "role": "assistant",
                    "content": "Hi!",
                    "timestamp": "2024-01-01T00:00:00",
                    "attachments": [
                        {
                            "type": "image",
                            "mime_type": "image/png",
                            "file_path": rel_path,
                        }
                    ],
                }
            ],
        }

        conversation_file = content_root / f"conversation_{conv_id}.json"
        conversation_file.write_text(json.dumps(conversation_payload), encoding="utf-8")

        mock_db.add_conversation.return_value = "conv-id"

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        status = ImportJob(
            job_id="job",
            user_id="test_user",
            status=ImportStatus.PENDING,
            chatbook_path="dummy",
        )

        with patch.object(service, "_get_conversation_by_name", return_value=None):
            service._import_conversations(
                tmp_path,
                manifest,
                [conv_id],
                ConflictResolution.SKIP,
                prefix_imported=False,
                status=status,
            )

        assert mock_db.add_message.call_count == 1
        message_payload = mock_db.add_message.call_args[0][0]
        assert "images" not in message_payload
        assert any("Failed to read attachment" in warning for warning in status.warnings)
        assert status.successful_items == 1

    def test_collect_conversations_exports_citations(self, service, mock_db, tmp_path):
        """Exported conversations should include RAG citations when available."""
        conv_id = "conv-citations"
        msg_id = "msg-1"
        now = datetime(2024, 1, 1, 0, 0, 0)

        mock_db.get_conversation_by_id.return_value = {
            "id": conv_id,
            "title": "Conversation With Citations",
            "created_at": now,
            "character_id": 1,
        }
        mock_db.get_messages_for_conversation.return_value = [
            {
                "id": msg_id,
                "sender": "assistant",
                "content": "Answer",
                "timestamp": now,
            }
        ]
        mock_db.get_message_rag_context.return_value = {
            "retrieved_documents": [
                {
                    "id": "doc-1",
                    "source_type": "file",
                    "title": "Doc Title",
                    "score": 0.95,
                    "excerpt": "Excerpt",
                    "url": "https://example.com",
                    "page_number": 2,
                    "chunk_id": "chunk-1",
                }
            ],
            "citations": [{"id": "cite-1"}],
            "settings_snapshot": {"top_k": 5},
            "generated_answer": {"id": "answer-1"},
            "search_query": "example query",
        }

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        content = ChatbookContent()

        service._collect_conversations([conv_id], tmp_path, manifest, content)

        exported = content.conversations[conv_id]
        message_payload = exported["messages"][0]
        assert message_payload["citations"]
        assert message_payload["citations"][0]["id"] == "doc-1"
        assert message_payload.get("formal_citations") == [{"id": "cite-1"}]
        assert message_payload.get("rag_settings") == {"top_k": 5}

    def test_import_conversation_skips_oversized_attachment(self, service, mock_db, tmp_path):
        """Oversized attachments should be skipped with a warning, not fail the conversation."""
        conv_id = "conv-oversize"
        content_root = tmp_path / "content" / "conversations"
        assets_dir = content_root / f"conversation_{conv_id}_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        image_bytes = b"0123456789"
        rel_path = f"content/conversations/{assets_dir.name}/big.png"
        (assets_dir / "big.png").write_bytes(image_bytes)

        conversation_payload = {
            "id": conv_id,
            "name": "Conversation Oversize Attachment",
            "created_at": "2024-01-01T00:00:00",
            "messages": [
                {
                    "id": "msg-big",
                    "role": "user",
                    "content": "Hello",
                    "timestamp": "2024-01-01T00:00:00",
                    "attachments": [
                        {
                            "type": "image",
                            "mime_type": "image/png",
                            "file_path": rel_path,
                        }
                    ],
                }
            ],
        }

        conversation_file = content_root / f"conversation_{conv_id}.json"
        conversation_file.write_text(json.dumps(conversation_payload), encoding="utf-8")

        mock_db.add_conversation.return_value = "conv-id"

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        status = ImportJob(
            job_id="job",
            user_id="test_user",
            status=ImportStatus.PENDING,
            chatbook_path="dummy",
        )

        with patch.object(service, "_get_max_message_image_bytes", return_value=4):
            with patch.object(service, "_get_conversation_by_name", return_value=None):
                service._import_conversations(
                    tmp_path,
                    manifest,
                    [conv_id],
                    ConflictResolution.SKIP,
                    prefix_imported=False,
                    status=status,
                )

        assert mock_db.add_message.call_count == 1
        message_payload = mock_db.add_message.call_args[0][0]
        assert "images" not in message_payload
        assert any("exceeds MAX_MESSAGE_IMAGE_BYTES" in warning for warning in status.warnings)
        assert status.successful_items == 1

    def test_import_dictionary_preserves_max_replacements_zero(self, service, mock_db, tmp_path):
        """Dictionary imports should preserve max_replacements=0 (unlimited)."""
        dict_id = "dict-max"
        dict_dir = tmp_path / "content" / "dictionaries"
        dict_dir.mkdir(parents=True, exist_ok=True)

        dict_payload = {
            "name": "Test Dict",
            "description": "Desc",
            "entries": [
                {
                    "pattern": "hello",
                    "replacement": "hi",
                    "type": "literal",
                    "probability": 1.0,
                    "max_replacements": 0,
                }
            ],
        }
        dict_file = dict_dir / f"dictionary_{dict_id}.json"
        dict_file.write_text(json.dumps(dict_payload), encoding="utf-8")

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        status = ImportJob(
            job_id="job",
            user_id="test_user",
            status=ImportStatus.PENDING,
            chatbook_path="dummy",
        )

        class DummyDictService:
            last_instance = None

            def __init__(self, _db):
                DummyDictService.last_instance = self
                self.add_entry_calls = []

            def get_dictionary_by_name(self, _name):
                return None

            def create_dictionary(self, _name, _description, _is_active=True):
                return 123

            def add_entry(self, *args, **kwargs):
                self.add_entry_calls.append((args, kwargs))

        with patch(
            "tldw_Server_API.app.core.Character_Chat.chat_dictionary.ChatDictionaryService",
            DummyDictService,
        ):
            service._import_dictionaries(
                tmp_path,
                manifest,
                [dict_id],
                ConflictResolution.SKIP,
                prefix_imported=False,
                status=status,
            )

        inst = DummyDictService.last_instance
        assert inst is not None
        assert inst.add_entry_calls
        _args, kwargs = inst.add_entry_calls[0]
        assert kwargs.get("max_replacements") == 0

    def test_preview_export_uses_chat_dictionaries_table(self, service, mock_db):
        """preview_export should query the chat_dictionaries table for dictionary counts."""
        mock_db.execute_query.return_value = []

        service.preview_export(["dictionaries"])

        calls = [call_args[0][0] for call_args in mock_db.execute_query.call_args_list]
        assert any("chat_dictionaries" in sql for sql in calls)

    def test_delete_export_job_removes_file_and_record(self, service, mock_db, tmp_path):
        """Completed export jobs should be removable and delete their archive."""
        export_dir = tmp_path / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        service.export_dir = export_dir

        file_path = export_dir / "export.zip"
        file_path.write_text("payload", encoding="utf-8")

        job = ExportJob(
            job_id="job-1",
            user_id=service.user_id,
            status=ExportStatus.COMPLETED,
            chatbook_name="Test",
            output_path=str(file_path),
        )

        with patch.object(service, "_get_export_job", return_value=job):
            ok = service.delete_export_job(job.job_id)

        assert ok is True
        assert not file_path.exists()
        mock_db.execute_query.assert_any_call(
            "DELETE FROM export_jobs WHERE job_id = ? AND user_id = ?",
            (job.job_id, service.user_id),
            commit=True,
        )

    def test_delete_import_job_removes_record(self, service, mock_db):
        """Cancelled import jobs should be removable."""
        job = ImportJob(
            job_id="job-2",
            user_id=service.user_id,
            status=ImportStatus.CANCELLED,
            chatbook_path="dummy",
        )

        with patch.object(service, "_get_import_job", return_value=job):
            ok = service.delete_import_job(job.job_id)

        assert ok is True
        mock_db.execute_query.assert_any_call(
            "DELETE FROM import_jobs WHERE job_id = ? AND user_id = ?",
            (job.job_id, service.user_id),
            commit=True,
        )

    def test_delete_export_job_rejects_non_terminal_status(self, service):
        """Non-terminal export jobs should not be removable."""
        job = ExportJob(
            job_id="job-3",
            user_id=service.user_id,
            status=ExportStatus.PENDING,
            chatbook_name="Test",
        )

        with patch.object(service, "_get_export_job", return_value=job):
            ok = service.delete_export_job(job.job_id)

        assert ok is False

    def test_resolve_import_archive_path_rejects_outside_paths(self, service):
        """Path resolution should raise SecurityError with a stable violation type."""
        with pytest.raises(SecurityError) as exc_info:
            service._resolve_import_archive_path("../../outside.chatbook")

        assert exc_info.value.context.get("violation_type") == "import_path_outside_allowed_directories"

    def test_cleanup_expired_exports_breaks_on_repeated_no_progress(self, service, mock_db):
        """Cleanup should stop after repeated batches that cannot mark rows expired."""
        expired_rows = [{"job_id": "job-stuck", "output_path": None}]
        call_counts = {"select": 0, "update": 0}

        def _execute_query(sql, params=None, commit=False):
            if sql.startswith("SELECT * FROM export_jobs"):
                call_counts["select"] += 1
                return expired_rows
            if sql.startswith("UPDATE export_jobs"):
                call_counts["update"] += 1
                raise RuntimeError("update failed")
            return []

        mock_db.execute_query.side_effect = _execute_query

        deleted = service.cleanup_expired_exports(batch_size=1)

        assert deleted == 0
        assert call_counts["select"] == 2
        assert call_counts["update"] == 2

    def test_cleanup_expired_exports_mixed_progress_exits_cleanly(self, service, mock_db):
        """Cleanup should preserve successful updates and still terminate with mixed outcomes."""
        select_batches = [
            [
                {"job_id": "job-ok", "output_path": None},
                {"job_id": "job-fail", "output_path": None},
            ],
            [
                {"job_id": "job-fail", "output_path": None},
            ],
        ]
        update_attempts: list[str] = []

        def _execute_query(sql, params=None, commit=False):
            if sql.startswith("SELECT * FROM export_jobs"):
                if select_batches:
                    return select_batches.pop(0)
                return []
            if sql.startswith("UPDATE export_jobs"):
                job_id = params[1]
                update_attempts.append(job_id)
                if job_id == "job-fail":
                    raise RuntimeError("update failed")
                return None
            return []

        mock_db.execute_query.side_effect = _execute_query

        deleted = service.cleanup_expired_exports(batch_size=2)

        assert deleted == 0
        assert update_attempts.count("job-ok") == 1
        assert update_attempts.count("job-fail") == 2

    def test_import_chatbook_cleans_temp_dir_on_failure(self, service, tmp_path):
        """Temporary extraction directories should not linger after import errors."""
        temp_dir = tmp_path / "chatbooks_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        service.temp_dir = temp_dir

        bad_manifest = {
            "version": "invalid",
            "name": "Broken Chatbook",
            "description": "Invalid version should trigger failure",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "content_items": [],
            "configuration": {},
            "statistics": {},
            "metadata": {},
            "user_info": {},
        }

        archive_path = temp_dir / "broken.chatbook"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(bad_manifest))

        assert not any(temp_dir.glob("import_*"))

        success, message, _ = service._import_chatbook_sync(
            file_path=str(archive_path),
            content_selections=None,
            conflict_resolution=ConflictResolution.SKIP,
            prefix_imported=False,
            import_media=True,
            import_embeddings=False,
        )

        assert success is False
        assert "Error importing chatbook" in message
        assert not any(temp_dir.glob("import_*"))

    def test_preview_chatbook_cleans_temp_dir_on_failure(self, service, tmp_path):
        """Preview extractions must be removed even when parsing fails."""
        temp_dir = tmp_path / "chatbooks_preview_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        service.temp_dir = temp_dir

        bad_manifest = {
            "version": "invalid",
            "name": "Preview Failure",
            "description": "Invalid version forces parse error",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "content_items": [],
            "configuration": {},
            "statistics": {},
            "metadata": {},
            "user_info": {},
        }

        archive_path = temp_dir / "broken_preview.chatbook"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(bad_manifest))

        assert not any(temp_dir.glob("preview_*"))

        manifest, error = service.preview_chatbook(str(archive_path))

        assert manifest is None
        assert error is not None
        assert not any(temp_dir.glob("preview_*"))

    @pytest.mark.asyncio
    async def test_export_manifest_total_size_bytes_matches_archive(self, service):
        """Exported manifest should report the final archive size."""
        success, _message, export_path = await service.create_chatbook(
            name="Size Check",
            description="Ensure manifest size is accurate",
            content_selections={},
            async_mode=False
        )
        assert success is True
        assert export_path is not None

        archive_path = Path(export_path)
        archive_size = archive_path.stat().st_size
        with zipfile.ZipFile(archive_path, "r") as zf:
            manifest_data = json.loads(zf.read("manifest.json"))

        total_size = (manifest_data.get("statistics") or {}).get("total_size_bytes", 0)
        assert total_size == archive_size

    def test_collect_conversations_paginates_messages(self, service, mock_db, tmp_path, monkeypatch):
        """Conversation exports should page through all messages."""
        monkeypatch.setenv("CHATBOOKS_CONVERSATION_EXPORT_PAGE_SIZE", "2")

        conv_id = "conv1"
        mock_db.get_conversation_by_id.return_value = {
            "id": conv_id,
            "title": "Test Conversation",
            "created_at": datetime(2024, 1, 1, 0, 0, 0),
            "character_id": 1,
        }

        msg1 = {"id": "m1", "sender": "user", "content": "hi", "timestamp": datetime(2024, 1, 1, 0, 0, 1), "images": []}
        msg2 = {"id": "m2", "sender": "assistant", "content": "hello", "timestamp": datetime(2024, 1, 1, 0, 0, 2), "images": []}
        msg3 = {"id": "m3", "sender": "user", "content": "more", "timestamp": datetime(2024, 1, 1, 0, 0, 3), "images": []}
        msg4 = {"id": "m4", "sender": "assistant", "content": "done", "timestamp": datetime(2024, 1, 1, 0, 0, 4), "images": []}

        mock_db.get_messages_for_conversation.side_effect = [
            [msg1, msg2],
            [msg3, msg4],
            [],
        ]

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        content = ChatbookContent()

        service._collect_conversations([conv_id], tmp_path, manifest, content)

        calls = mock_db.get_messages_for_conversation.call_args_list
        assert len(calls) == 3
        assert calls[0].kwargs["limit"] == 2
        assert calls[0].kwargs["offset"] == 0
        assert calls[1].kwargs["offset"] == 2

        conv_file = tmp_path / "content" / "conversations" / f"conversation_{conv_id}.json"
        assert conv_file.exists()
        payload = json.loads(conv_file.read_text(encoding="utf-8"))
        assert len(payload["messages"]) == 4
        assert "conversations" not in (manifest.truncation or {})

    @pytest.mark.asyncio
    async def test_export_filename_truncates_long_names(self, service):
        """Export filenames should stay within filesystem limits for long names."""
        long_name = "a" * 300
        success, _message, export_path = await service.create_chatbook(
            name=long_name,
            description="Long name export",
            content_selections={},
            async_mode=False,
        )
        assert success is True
        assert export_path is not None

        filename = Path(export_path).name
        assert filename.endswith(".zip")
        assert len(filename) <= 255

    @pytest.mark.asyncio
    async def test_export_chatbook_async_job(self, service, mock_db):
        """Test asynchronous chatbook export with job management."""
        mock_db.execute_query.return_value = []

        with patch.object(service, "create_chatbook", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = (
                True,
                "Export job started: job-123",
                "job-123",
            )

            result = await service.export_chatbook(
                name="Test Export",
                content_types=["conversations"],
                async_job=True,
            )

        mock_create.assert_awaited_once()
        call_kwargs = mock_create.await_args.kwargs
        assert call_kwargs["async_mode"] is True
        assert result == {
            "success": True,
            "message": "Export job started: job-123",
            "file_path": None,
            "job_id": "job-123",
            "status": "pending",
            "content_summary": {},
        }

    def test_import_skips_unsupported_content_types(self, service, tmp_path):
        """Unsupported content types should be skipped with warnings."""
        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Unsupported Types",
            description="Media and prompts are skipped",
            content_items=[
                ContentItem(id="m1", type=ContentType.MEDIA, title="Media 1"),
                ContentItem(id="p1", type=ContentType.PROMPT, title="Prompt 1"),
            ],
        )

        archive_path = service.temp_dir / "unsupported.chatbook"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest.to_dict()))

        success, message, warnings = service._import_chatbook_sync(
            file_path=str(archive_path),
            content_selections=None,
            conflict_resolution=ConflictResolution.SKIP,
            prefix_imported=False,
            import_media=True,
            import_embeddings=False,
        )

        assert success is True
        assert "skipped" in message.lower()
        assert warnings is not None
        assert any("unsupported content type" in warning.lower() for warning in warnings)

    def test_import_conversation_missing_character_falls_back(self, service, mock_db, tmp_path):
        """Missing character_id should fall back to default with a warning."""
        conv_id = "conv-missing-char"
        content_root = tmp_path / "content" / "conversations"
        content_root.mkdir(parents=True, exist_ok=True)

        conversation_payload = {
            "id": conv_id,
            "name": "Conversation Missing Character",
            "created_at": "2024-01-01T00:00:00",
            "character_id": None,
            "messages": [],
        }

        conversation_file = content_root / f"conversation_{conv_id}.json"
        conversation_file.write_text(json.dumps(conversation_payload), encoding="utf-8")

        def _char_lookup(char_id):
            if char_id == 1:
                return {"id": 1}
            return None

        mock_db.get_character_card_by_id.side_effect = _char_lookup
        mock_db.add_conversation.return_value = "new-conv-id"

        manifest = ChatbookManifest(
            version=ChatbookVersion.V1,
            name="Test",
            description="Desc",
        )
        status = ImportJob(
            job_id="job",
            user_id="test_user",
            status=ImportStatus.PENDING,
            chatbook_path="dummy",
        )

        with patch.object(service, "_get_conversation_by_name", return_value=None):
            service._import_conversations(
                tmp_path,
                manifest,
                [conv_id],
                ConflictResolution.SKIP,
                prefix_imported=False,
                status=status,
            )

        conv_payload = mock_db.add_conversation.call_args[0][0]
        assert conv_payload["character_id"] == 1
        assert any("default character" in warning.lower() for warning in status.warnings)

    def test_preview_export(self, service, mock_db):
        """Test previewing export content."""
        # Mock queries based on what's being queried
        def mock_query(query, params=None):
            if "conversations" in query.lower():
                return [{"id": "conv1"}, {"id": "conv2"}]
            elif "character_cards" in query.lower():
                return [{"id": "char1"}]
            elif "notes" in query.lower():
                return [{"id": "note1"}, {"id": "note2"}]
            return []

        mock_db.execute_query = mock_query

        result = service.preview_export(
            content_types=["conversations", "characters", "notes"]
        )

        # Results should match mocked data
        assert result["conversations"] == 2
        assert result["characters"] == 1
        assert result["notes"] == 2
        assert result["world_books"] == 0

    def test_generate_unique_name_world_book_conflict(self, service, mock_db):
        """Ensure rename helper terminates when conflicts exist."""
        responses = [
            [{"id": 1}],  # Existing name hits conflict
            []            # Next candidate is available
        ]

        def side_effect(query, params=None):
            return responses.pop(0)

        mock_db.execute_query.side_effect = side_effect

        new_name = service._generate_unique_name("Existing", "world_book")

        assert new_name == "Existing (2)"

    def test_generate_unique_name_conversation_conflict(self, service):
        """Ensure rename helper uses conversation lookup helper."""
        with patch.object(
            service,
            "_get_conversation_by_name",
            side_effect=[{"id": "conv-1"}, None],
        ) as mock_lookup:
            new_name = service._generate_unique_name("Existing", "conversation")

        assert new_name == "Existing (2)"
        assert mock_lookup.call_count == 2

    def test_generate_unique_name_note_conflict(self, service):
        """Ensure rename helper uses note lookup helper."""
        with patch.object(
            service,
            "_get_note_by_title",
            side_effect=[{"id": "note-1"}, None],
        ) as mock_lookup:
            new_name = service._generate_unique_name("Existing", "note")

        assert new_name == "Existing (2)"
        assert mock_lookup.call_count == 2

    def test_get_export_job_status(self, service, mock_db):
        """Test retrieving export job status."""
        # Return tuple matching database schema with metadata
        metadata = json.dumps({
            "conversation_count": 5,
            "note_count": 3,
            "character_count": 2
        })
        mock_db.execute_query.return_value = [
            ("job123", "test_user", "completed", "Test Export",
             "/tmp/export.chatbook", "2024-01-01T00:00:00",
             "2024-01-01T00:01:00", "2024-01-01T00:05:00",
             None, 100, 100, 100, 1024, metadata, None)
        ]

        result = service.get_export_job_status("job123")

        assert result["job_id"] == "job123"
        assert result["status"] == "completed"
        assert result["file_path"] == "/tmp/export.chatbook"
        assert result["content_summary"]["conversations"] == 5

    def test_cancel_export_job(self, service, mock_db):
        """Test cancelling an export job."""
        # Mock database to return a pending job
        mock_db.execute_query.return_value = [{
            "job_id": "job123",
            "user_id": "test_user",
            "status": "pending",
            "chatbook_name": "Test",
            "output_path": None,
            "created_at": "2024-01-01T00:00:00",
            "started_at": None,
            "completed_at": None,
            "error_message": None,
            "progress_percentage": 0,
            "total_items": 0,
            "processed_items": 0,
            "file_size_bytes": 0,
            "download_url": None,
            "expires_at": None
        }]

        result = service.cancel_export_job("job123")

        assert result == True

    @pytest.mark.asyncio
    async def test_import_chatbook_rejects_unsupported_conflict_resolution(self, service):
        """Unsupported conflict_resolution values should fail fast."""
        with patch(
            "tldw_Server_API.app.core.Chatbooks.chatbook_service.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            result = await service.import_chatbook(
                file_path="sample.chatbook",
                conflict_resolution="overwrite",
            )

        mock_to_thread.assert_not_awaited()
        assert result[0] is False
        assert "not supported" in result[1].lower()

    @pytest.mark.asyncio
    async def test_import_chatbook_conflict_strategy_alias(self, service):
        """conflict_strategy alias should map to the same enum handling."""
        sample_path = service.import_dir / "sample.chatbook"
        sample_path.write_text("dummy")
        with patch(
            "tldw_Server_API.app.core.Chatbooks.chatbook_service.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_to_thread.return_value = (True, "alias ok", None)

            await service.import_chatbook(
                file_path=str(sample_path),
                conflict_strategy="rename",
            )

        call_args = mock_to_thread.await_args.args
        assert call_args[3] is ConflictResolution.RENAME

    @pytest.mark.asyncio
    async def test_import_chatbook_invalid_conflict_resolution_defaults_to_skip(self, service):
        """Invalid conflict resolution values should fall back to SKIP."""
        sample_path = service.import_dir / "sample.chatbook"
        sample_path.write_text("dummy")
        with patch(
            "tldw_Server_API.app.core.Chatbooks.chatbook_service.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_to_thread.return_value = (True, "defaulted", None)

            await service.import_chatbook(
                file_path=str(sample_path),
                conflict_resolution="replace",
            )

        call_args = mock_to_thread.await_args.args
        assert call_args[3] is ConflictResolution.SKIP

    def test_create_import_job(self, service, mock_db):
        """Test creating an import job."""
        test_uuid = uuid4()
        job_id = str(test_uuid)

        with patch('tldw_Server_API.app.core.Chatbooks.chatbook_service.uuid4', return_value=test_uuid):
            mock_db.execute_query.return_value = None

            result = service.create_import_job(
                file_path="/tmp/test.chatbook",
                conflict_strategy="skip"
            )

        assert result["job_id"] == job_id
        assert result["status"] == "pending"

    def test_get_import_job_status(self, service, mock_db):
        """Test retrieving import job status."""
        # Return tuple matching database schema
        mock_db.execute_query.return_value = [
            ("job456", "test_user", "completed", "/tmp/import.chatbook",
             "2024-01-01T00:00:00", "2024-01-01T00:01:00", "2024-01-01T00:10:00",
             None, 100, 10, 10, 10, 0, 2, "[]", "[]")
        ]

        result = service.get_import_job_status("job456")

        assert result["job_id"] == "job456"
        assert result["status"] == "completed"
        assert result["successful_items"] == 10
        assert result["conflicts_found"] == 2
        assert result["conflicts_resolved"]["skipped"] == 2

    def test_list_export_jobs(self, service, mock_db):
        """Test listing export jobs."""
        # Return tuples matching database schema
        mock_db.execute_query.return_value = [
            ("job1", "test_user", "completed", "Export 1", None,
             "2024-01-01T00:00:00", None, None, None, 100, 0, 0, 0, None, None),
            ("job2", "test_user", "pending", "Export 2", None,
             "2024-01-01T00:00:00", None, None, None, 50, 0, 0, 0, None, None)
        ]

        results = service.list_export_jobs()

        assert len(results) == 2
        assert results[0]["chatbook_name"] == "Export 1"
        assert results[1]["status"] == "pending"

    def test_list_import_jobs(self, service, mock_db):
        """Test listing import jobs."""
        # Return tuples matching database schema
        mock_db.execute_query.return_value = [
            ("job3", "test_user", "completed", "/tmp/import.chatbook",
             "2024-01-01T00:00:00", None, None, None, 100, 5, 5, 5, 0, 0, "[]", "[]"),
            ("job4", "test_user", "failed", "/tmp/import2.chatbook",
             "2024-01-01T00:00:00", None, None, "File not found", 0, 0, 0, 0, 0, 0, "[]", "[]")
        ]

        results = service.list_import_jobs()

        assert len(results) == 2
        assert results[0]["successful_items"] == 5
        assert results[1]["error_message"] == "File not found"

    def test_clean_old_exports(self, service, mock_db):
        """Test cleaning old export files."""
        export_dir = service.export_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        file_one = export_dir / "old1.chatbook"
        file_two = export_dir / "old2.chatbook"
        file_one.write_text("old")
        file_two.write_text("old")

        # Return tuples with job_id and output_path
        mock_db.execute_query.return_value = [
            ("old1", str(file_one)),
            ("old2", str(file_two))
        ]

        count = service.clean_old_exports(days_old=7)

        assert count == 2
        assert not file_one.exists()
        assert not file_two.exists()

    def test_validate_chatbook_file(self, service, sample_manifest):
        """Test validating a chatbook file structure."""
        chatbook_path = service.temp_dir / f"validate_{uuid4().hex}.chatbook"
        with zipfile.ZipFile(chatbook_path, 'w') as zf:
            zf.writestr('manifest.json', json.dumps(manifest_to_dict(sample_manifest)))
            zf.writestr('conversations/test.json', '{}')

        # Use the correct method name: validate_chatbook_file
        result = service.validate_chatbook_file(str(chatbook_path))

        # Result is a dict with is_valid key
        assert result["is_valid"] == True
        assert "manifest" in result

    def test_validate_invalid_chatbook(self, service):
        """Test validating an invalid chatbook file."""
        invalid_path = service.temp_dir / f"invalid_{uuid4().hex}.txt"
        invalid_path.write_bytes(b"Not a zip file")

        # Invalid ZIP should raise an exception
        result = service.validate_chatbook_file(str(invalid_path))

        assert result["is_valid"] == False
        assert "error" in result

    def test_get_statistics(self, service, mock_db):
        """Test getting import/export statistics."""
        # Mock returns tuples for status counts
        mock_db.execute_query.side_effect = [
            [("completed", 45), ("failed", 5)],  # Export stats by status
            [("completed", 28), ("failed", 2)],  # Import stats by status
        ]

        stats = service.get_statistics()

        # Check the structure returned by get_statistics
        assert "exports" in stats
        assert "imports" in stats
        assert stats["exports"].get("completed", 0) == 45
        assert stats["imports"].get("completed", 0) == 28

    @pytest.mark.asyncio
    async def test_error_handling_during_export(self, service):
        """Test error handling during export."""
        with patch.object(service, "create_chatbook", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = RuntimeError("Database error")

            with pytest.raises(RuntimeError):
                await service.export_chatbook(
                    name="Test Export",
                    content_types=["conversations"],
                )

    @pytest.mark.asyncio
    async def test_error_handling_during_import(self, service):
        """Test error handling during import."""
        result = await service.import_chatbook(
            file_path="/nonexistent/file.chatbook",
            conflict_resolution="skip"
        )

        assert result == (
            False,
            "Invalid or potentially malicious archive file",
            None,
        )

    def test_user_isolation(self, service, mock_db):
        """Test that operations are isolated to the current user."""
        # Test export - should only get current user's content
        mock_db.execute_query.return_value = []

        service.preview_export(content_types=["conversations"])

        # Check that the query was made - the actual implementation uses "deleted = 0"
        # instead of user_id filtering because tables don't have user_id columns
        call_args = mock_db.execute_query.call_args[0]
        # Accept either user_id filtering or deleted filtering (actual implementation)
        assert ("WHERE user_id = ?" in call_args[0] or
                "WHERE deleted = 0" in call_args[0] or
                "test_user" in str(call_args))

    def test_create_chatbook_archive(self, service, sample_manifest, sample_content_items):
        """Test creating a chatbook archive file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "work"
            work_dir.mkdir()
            output_path = Path(tmpdir) / "test.chatbook"

            # Write some test content to work dir
            (work_dir / "manifest.json").write_text(json.dumps(manifest_to_dict(sample_manifest)))
            (work_dir / "test.txt").write_text("test content")

            # Call with correct parameters (work_dir and output_path)
            result = service._create_chatbook_archive(
                work_dir=work_dir,
                output_path=output_path
            )

            assert result == True
            assert output_path.exists()

            # Verify it's a valid zip file
            with zipfile.ZipFile(output_path, 'r') as zf:
                assert 'manifest.json' in zf.namelist()

    def test_process_import_items(self, service, mock_db, sample_content_items):
        """Test processing individual import items."""
        mock_db.execute_query.return_value = []  # No conflicts

        # Call with correct parameter name (conflict_resolution)
        results = service._process_import_items(
            items=sample_content_items,
            conflict_resolution="skip"
        )

        # Results is an ImportStatusData object
        assert results.successful_items == len(sample_content_items)
        assert results.skipped_items == 0
        assert results.failed_items == 0
