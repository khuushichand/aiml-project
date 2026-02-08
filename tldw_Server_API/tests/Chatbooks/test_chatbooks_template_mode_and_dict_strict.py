import json

import pytest

from tldw_Server_API.app.core.Chatbooks.chatbook_models import (
    ChatbookContent,
    ChatbookManifest,
    ChatbookVersion,
    ConflictResolution,
    ImportJob,
    ImportStatus,
)
from tldw_Server_API.app.core.Chatbooks.chatbook_service import ChatbookService
from tldw_Server_API.app.core.Character_Chat.chat_dictionary import ChatDictionaryService
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


def _manifest(
    *,
    mode: str,
    defaults: dict | None = None,
    timezone: str = "UTC",
    locale: str = "en_US",
) -> ChatbookManifest:
    return ChatbookManifest(
        version=ChatbookVersion.V1,
        name="Template Test",
        description="Template behavior",
        metadata={
            "template_mode": mode,
            "template_defaults": defaults or {},
            "template_timezone": timezone,
            "template_locale": locale,
        },
    )


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path))
    db_path = tmp_path / "chatbooks_template_modes.db"
    return CharactersRAGDB(str(db_path), "test_user")


@pytest.fixture
def service(db):
    return ChatbookService(user_id="test_user", db=db)


@pytest.mark.unit
def test_notes_render_on_export(service, db, tmp_path):
    note_id = db.add_note(
        title="Daily {{ project }}",
        content="Summary for {{ project }}",
    )
    manifest = _manifest(mode="render_on_export", defaults={"project": "Apollo"})
    content = ChatbookContent()
    work_dir = tmp_path / "export_render"
    work_dir.mkdir(parents=True, exist_ok=True)

    service._collect_notes([str(note_id)], work_dir, manifest, content)

    note_file = work_dir / "content" / "notes" / f"note_{note_id}.md"
    exported_text = note_file.read_text(encoding="utf-8")
    assert "Daily Apollo" in exported_text
    assert "Summary for Apollo" in exported_text
    assert "{{ project }}" not in exported_text


@pytest.mark.unit
def test_notes_pass_through_on_export(service, db, tmp_path):
    note_id = db.add_note(
        title="Daily {{ project }}",
        content="Summary for {{ project }}",
    )
    manifest = _manifest(mode="pass_through", defaults={"project": "Apollo"})
    content = ChatbookContent()
    work_dir = tmp_path / "export_passthrough"
    work_dir.mkdir(parents=True, exist_ok=True)

    service._collect_notes([str(note_id)], work_dir, manifest, content)

    note_file = work_dir / "content" / "notes" / f"note_{note_id}.md"
    exported_text = note_file.read_text(encoding="utf-8")
    assert "Daily {{ project }}" in exported_text
    assert "Summary for {{ project }}" in exported_text


@pytest.mark.unit
def test_notes_render_on_import(service, db, tmp_path):
    manifest = _manifest(mode="render_on_import", defaults={"project": "Apollo"})
    extract_dir = tmp_path / "import_render"
    notes_dir = extract_dir / "content" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_file = notes_dir / "note_1.md"
    note_file.write_text(
        "---\n"
        "id: 1\n"
        "title: Daily {{ project }}\n"
        "created_at: 2026-01-01T00:00:00\n"
        "---\n\n"
        "Summary for {{ project }}",
        encoding="utf-8",
    )

    status = ImportJob(
        job_id="job-notes-import",
        user_id="test_user",
        status=ImportStatus.IN_PROGRESS,
        chatbook_path="dummy",
    )
    service._import_notes(
        extract_dir,
        manifest,
        ["1"],
        ConflictResolution.SKIP,
        prefix_imported=False,
        status=status,
    )

    imported = db.list_notes(limit=10, offset=0)
    assert len(imported) == 1
    assert imported[0]["title"] == "Daily Apollo"
    assert "Summary for Apollo" in imported[0]["content"]


@pytest.mark.unit
def test_import_dict_strict_skips_only_fatal(service, db, tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOOKS_IMPORT_DICT_STRICT", "1")
    manifest = _manifest(mode="pass_through")

    extract_dir = tmp_path / "import_dict_strict"
    dict_dir = extract_dir / "content" / "dictionaries"
    dict_dir.mkdir(parents=True, exist_ok=True)

    non_fatal_payload = {
        "name": "NonFatal Dict",
        "description": "Should still import under strict mode",
        "entries": [
            {
                "type": "literal",
                "pattern": "hello",
                "replacement": "hi",
                "probability": 2.0,
            }
        ],
    }
    fatal_payload = {
        "name": "Fatal Dict",
        "description": "Should be skipped under strict mode",
        "entries": [
            {
                "type": "regex",
                "pattern": "(",
                "replacement": "broken",
            }
        ],
    }

    (dict_dir / "dictionary_1.json").write_text(json.dumps(non_fatal_payload), encoding="utf-8")
    (dict_dir / "dictionary_2.json").write_text(json.dumps(fatal_payload), encoding="utf-8")

    status = ImportJob(
        job_id="job-dicts-strict",
        user_id="test_user",
        status=ImportStatus.IN_PROGRESS,
        chatbook_path="dummy",
    )
    service._import_dictionaries(
        extract_dir,
        manifest,
        ["1", "2"],
        ConflictResolution.SKIP,
        prefix_imported=False,
        status=status,
    )

    dict_service = ChatDictionaryService(db)
    names = {row.get("name") for row in dict_service.list_dictionaries(include_inactive=True)}

    assert "NonFatal Dict" in names
    assert "Fatal Dict" not in names
    assert status.successful_items == 1
    assert status.skipped_items == 1
    assert status.failed_items == 0
    assert any("fatal errors" in w.lower() for w in status.warnings)


@pytest.mark.unit
def test_import_dict_render_on_import_with_global_template_flag(service, db, tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_DICT_TEMPLATES_ENABLED", "1")
    manifest = _manifest(mode="render_on_import", defaults={"project": "Apollo"})

    extract_dir = tmp_path / "import_dict_render"
    dict_dir = extract_dir / "content" / "dictionaries"
    dict_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "name": "Template Dict",
        "description": "",
        "entries": [
            {
                "type": "literal",
                "pattern": "hello",
                "replacement": "Hello {{ project }}",
            }
        ],
    }
    (dict_dir / "dictionary_10.json").write_text(json.dumps(payload), encoding="utf-8")

    status = ImportJob(
        job_id="job-dicts-render",
        user_id="test_user",
        status=ImportStatus.IN_PROGRESS,
        chatbook_path="dummy",
    )
    service._import_dictionaries(
        extract_dir,
        manifest,
        ["10"],
        ConflictResolution.SKIP,
        prefix_imported=False,
        status=status,
    )

    dict_service = ChatDictionaryService(db)
    dictionaries = dict_service.list_dictionaries(include_inactive=True)
    template_dict = next((d for d in dictionaries if d.get("name") == "Template Dict"), None)
    assert template_dict is not None
    entries = dict_service.get_entries(int(template_dict["id"]), active_only=False)
    assert len(entries) == 1
    assert entries[0]["content"] == "Hello Apollo"
