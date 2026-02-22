from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB, SemanticMemory
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Persona.memory_integration import (
    persist_persona_turn,
    persist_tool_outcome,
    retrieve_top_memories,
)


pytestmark = pytest.mark.unit


def _seed_memory_db(tmp_path, monkeypatch, *, user_id: str, enabled: bool) -> PersonalizationDB:
    base = tmp_path / "user_db"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))
    path = DatabasePaths.get_personalization_db_path(int(user_id))
    db = PersonalizationDB(str(path))
    db.update_profile(user_id, enabled=1 if enabled else 0)
    return db


def test_retrieve_top_memories_respects_opt_in_and_top_k(tmp_path, monkeypatch):
    user_id = "101"
    db = _seed_memory_db(tmp_path, monkeypatch, user_id=user_id, enabled=True)
    _ = db.add_semantic_memory(
        SemanticMemory(user_id=user_id, content="Prefers concise responses.", tags=["prefs"])
    )
    _ = db.add_semantic_memory(
        SemanticMemory(user_id=user_id, content="Working on FastAPI tests.", tags=["project"])
    )

    memories = retrieve_top_memories(user_id=user_id, query_text="FastAPI", top_k=1)
    assert len(memories) == 1
    assert "FastAPI" in memories[0].content


def test_retrieve_top_memories_returns_empty_when_opted_out(tmp_path, monkeypatch):
    user_id = "102"
    db = _seed_memory_db(tmp_path, monkeypatch, user_id=user_id, enabled=False)
    _ = db.add_semantic_memory(
        SemanticMemory(user_id=user_id, content="Should not be used when opted out.", tags=["prefs"])
    )

    memories = retrieve_top_memories(user_id=user_id, query_text="used", top_k=3)
    assert memories == []


def test_persist_turn_and_tool_outcome_when_opted_in(tmp_path, monkeypatch):
    user_id = "103"
    db = _seed_memory_db(tmp_path, monkeypatch, user_id=user_id, enabled=True)
    session_id = "sess_memory"

    ok_turn = persist_persona_turn(
        user_id=user_id,
        session_id=session_id,
        persona_id="research_assistant",
        role="assistant",
        content="Here is your summary.",
        turn_type="assistant_delta",
        metadata={"source": "test"},
        store_as_memory=True,
    )
    ok_tool = persist_tool_outcome(
        user_id=user_id,
        session_id=session_id,
        persona_id="research_assistant",
        tool_name="rag_search",
        step_idx=0,
        outcome={"ok": True, "result": {"hits": 2}},
    )
    assert ok_turn is True
    assert ok_tool is True

    events = db.list_recent_events(user_id=user_id, limit=20)
    assert len(events) >= 2
    assert any(evt["type"] == "persona.turn" for evt in events)

    memories, _ = db.list_semantic_memories(user_id=user_id, limit=20, offset=0)
    contents = [item["content"] for item in memories]
    assert any("Here is your summary." in c for c in contents)
    assert any("Tool=rag_search" in c for c in contents)


def test_persist_turn_skips_when_opted_out(tmp_path, monkeypatch):
    user_id = "104"
    db = _seed_memory_db(tmp_path, monkeypatch, user_id=user_id, enabled=False)
    session_id = "sess_memory_off"

    ok_turn = persist_persona_turn(
        user_id=user_id,
        session_id=session_id,
        persona_id="research_assistant",
        role="assistant",
        content="Should not persist.",
        turn_type="assistant_delta",
        metadata=None,
        store_as_memory=True,
    )
    assert ok_turn is False
    assert db.list_recent_events(user_id=user_id, limit=10) == []
    memories, total = db.list_semantic_memories(user_id=user_id, limit=10, offset=0)
    assert total == 0
    assert memories == []

