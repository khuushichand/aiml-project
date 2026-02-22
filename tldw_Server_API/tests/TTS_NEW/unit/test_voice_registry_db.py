"""Unit tests for persistent voice registry storage."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from tldw_Server_API.app.core.DB_Management.Voice_Registry_DB import VoiceRegistryDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def _voice_record(voice_id: str, *, name: str | None = None, file_path: str | None = None) -> dict[str, object]:
    return {
        "voice_id": voice_id,
        "name": name or voice_id,
        "description": f"description-{voice_id}",
        "file_path": file_path or f"processed/{voice_id}.wav",
        "format": "wav",
        "duration": 3.5,
        "sample_rate": 22050,
        "size_bytes": 1024,
        "provider": "vibevoice",
        "created_at": datetime.utcnow().isoformat(),
        "file_hash": f"hash-{voice_id}",
    }


def test_voice_registry_db_crud_and_replace(tmp_path, monkeypatch):
    monkeypatch.setattr(
        DatabasePaths,
        "get_user_db_base_dir",
        lambda *args, **kwargs: tmp_path,
        raising=True,
    )
    db = VoiceRegistryDB(tmp_path / "voice_registry.db")

    db.upsert_voice(1, _voice_record("voice-a", name="Alpha"))
    db.upsert_voice(1, _voice_record("voice-b", name="Bravo"))

    rows = db.list_voices(1)
    ids = {row["voice_id"] for row in rows}
    assert ids == {"voice-a", "voice-b"}

    fetched = db.get_voice(1, "voice-a")
    assert fetched is not None
    assert fetched["name"] == "Alpha"

    db.replace_user_voices(
        1,
        [
            _voice_record("voice-b", name="Bravo-updated"),
            _voice_record("voice-c", name="Charlie"),
        ],
    )
    replaced_ids = {row["voice_id"] for row in db.list_voices(1)}
    assert replaced_ids == {"voice-b", "voice-c"}
    assert db.get_voice(1, "voice-a") is None
    assert db.get_voice(1, "voice-b")["name"] == "Bravo-updated"

    assert db.delete_voice(1, "voice-c") is True
    assert db.delete_voice(1, "voice-c") is False


def test_voice_registry_db_migrates_legacy_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(
        DatabasePaths,
        "get_user_db_base_dir",
        lambda *args, **kwargs: tmp_path,
        raising=True,
    )
    db_path = tmp_path / "voice_registry.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE voice_registry (
                user_id INTEGER NOT NULL,
                voice_id TEXT NOT NULL,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                format TEXT NOT NULL,
                duration REAL NOT NULL DEFAULT 0,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                provider TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, voice_id)
            )
            """
        )
        conn.commit()

    db = VoiceRegistryDB(db_path)
    db.upsert_voice(2, _voice_record("legacy-voice", name="Legacy"))
    row = db.get_voice(2, "legacy-voice")
    assert row is not None
    assert row["description"] == "description-legacy-voice"
    assert row["file_hash"] == "hash-legacy-voice"
