import pytest

from tldw_Server_API.app.core.Persona.session_manager import SessionManager


pytestmark = pytest.mark.unit


def test_session_manager_plan_roundtrip_and_consume():
    manager = SessionManager()
    manager.put_plan(
        session_id="sess_1",
        user_id="user_1",
        persona_id="research_assistant",
        plan_id="plan_1",
        steps=[
            {"idx": 1, "tool": "summarize", "args": {}},
            {"idx": 0, "tool": "rag_search", "args": {"query": "hello"}},
        ],
    )

    pending = manager.get_plan(session_id="sess_1", plan_id="plan_1", user_id="user_1")
    assert pending is not None
    assert [step.idx for step in pending.steps] == [0, 1]

    consumed = manager.get_plan(
        session_id="sess_1",
        plan_id="plan_1",
        user_id="user_1",
        consume=True,
    )
    assert consumed is not None
    assert manager.get_plan(session_id="sess_1", plan_id="plan_1", user_id="user_1") is None


def test_session_manager_plan_lookup_rejects_session_or_user_mismatch():
    manager = SessionManager()
    manager.put_plan(
        session_id="sess_1",
        user_id="user_1",
        persona_id="research_assistant",
        plan_id="plan_1",
        steps=[{"idx": 0, "tool": "rag_search", "args": {"query": "hello"}}],
    )

    assert manager.get_plan(session_id="sess_2", plan_id="plan_1", user_id="user_1") is None
    assert manager.get_plan(session_id="sess_1", plan_id="plan_1", user_id="user_2") is None


def test_session_manager_rejects_resume_session_owner_mismatch():
    manager = SessionManager()
    _ = manager.create(user_id="user_1", persona_id="research_assistant", resume_session_id="sess_1")

    with pytest.raises(ValueError, match="ownership mismatch"):
        manager.create(user_id="user_2", persona_id="research_assistant", resume_session_id="sess_1")


def test_session_manager_clear_plans():
    manager = SessionManager()
    manager.put_plan(
        session_id="sess_clear",
        user_id="user_1",
        persona_id="research_assistant",
        plan_id="plan_1",
        steps=[{"idx": 0, "tool": "rag_search", "args": {"query": "hello"}}],
    )
    manager.put_plan(
        session_id="sess_clear",
        user_id="user_1",
        persona_id="research_assistant",
        plan_id="plan_2",
        steps=[{"idx": 0, "tool": "summarize", "args": {}}],
    )

    cleared = manager.clear_plans(session_id="sess_clear", user_id="user_1")
    assert cleared == 2
    assert manager.get_plan(session_id="sess_clear", plan_id="plan_1", user_id="user_1") is None
    assert manager.get_plan(session_id="sess_clear", plan_id="plan_2", user_id="user_1") is None


def test_session_manager_turn_append_and_list_limit():
    manager = SessionManager()
    manager.append_turn(
        session_id="sess_turns",
        user_id="user_1",
        persona_id="research_assistant",
        role="user",
        content="hello",
        turn_type="user_message",
    )
    manager.append_turn(
        session_id="sess_turns",
        user_id="user_1",
        persona_id="research_assistant",
        role="assistant",
        content="hi there",
        turn_type="assistant_delta",
    )

    turns = manager.list_turns(session_id="sess_turns", user_id="user_1")
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["role"] == "assistant"

    limited = manager.list_turns(session_id="sess_turns", user_id="user_1", limit=1)
    assert len(limited) == 1
    assert limited[0]["role"] == "assistant"


def test_session_manager_list_sessions_and_snapshot():
    manager = SessionManager()
    manager.append_turn(
        session_id="sess_1",
        user_id="user_1",
        persona_id="research_assistant",
        role="user",
        content="hello",
        turn_type="user_message",
    )
    manager.append_turn(
        session_id="sess_2",
        user_id="user_1",
        persona_id="research_assistant",
        role="user",
        content="another",
        turn_type="user_message",
    )
    manager.append_turn(
        session_id="sess_3",
        user_id="user_2",
        persona_id="research_assistant",
        role="user",
        content="foreign",
        turn_type="user_message",
    )

    listed = manager.list_sessions(user_id="user_1")
    assert len(listed) == 2
    assert all(item["session_id"] in {"sess_1", "sess_2"} for item in listed)
    assert all(item["turn_count"] == 1 for item in listed)

    snapshot = manager.get_session_snapshot(session_id="sess_1", user_id="user_1", limit_turns=10)
    assert snapshot is not None
    assert snapshot["session_id"] == "sess_1"
    assert snapshot["turn_count"] == 1
    assert len(snapshot["turns"]) == 1

    assert manager.get_session_snapshot(session_id="sess_1", user_id="user_2") is None


def test_session_manager_preferences_roundtrip():
    manager = SessionManager()
    _ = manager.create(user_id="user_1", persona_id="research_assistant", resume_session_id="sess_prefs")

    updated = manager.update_preferences(
        session_id="sess_prefs",
        user_id="user_1",
        preferences={"use_memory_context": False, "memory_top_k": 2},
    )
    assert updated["use_memory_context"] is False
    assert updated["memory_top_k"] == 2

    prefs = manager.get_preferences(session_id="sess_prefs", user_id="user_1")
    assert prefs["use_memory_context"] is False
    assert prefs["memory_top_k"] == 2

    with pytest.raises(ValueError, match="ownership mismatch"):
        manager.update_preferences(
            session_id="sess_prefs",
            user_id="user_2",
            preferences={"use_memory_context": True},
        )
