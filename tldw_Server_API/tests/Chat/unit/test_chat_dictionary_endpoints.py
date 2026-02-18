from __future__ import annotations

import datetime

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoints
from tldw_Server_API.app.api.v1.schemas.chat_dictionary_schemas import (
    BulkEntryOperation,
    ChatDictionaryCreate,
    ChatDictionaryUpdate,
    DictionaryEntryCreate,
    DictionaryEntryReorderRequest,
    DictionaryEntryUpdate,
    ProcessTextRequest,
)
from tldw_Server_API.app.core.Character_Chat.chat_dictionary import ChatDictionaryService
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture()
def chacha_db(tmp_path):
    db_path = tmp_path / "ChaChaNotes.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="test-client")
    try:
        yield db
    finally:
        db.close_connection()


@pytest.mark.asyncio
async def test_add_dictionary_entry_returns_persisted_fields(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Test Dictionary", "Description")

    entry_create = DictionaryEntryCreate(pattern="hello", replacement="world")
    response = await chat_endpoints.add_dictionary_entry(dictionary_id, entry_create, db=chacha_db)

    assert response.dictionary_id == dictionary_id
    assert response.pattern == "hello"
    assert response.replacement == "world"
    assert isinstance(response.created_at, datetime.datetime)
    assert isinstance(response.updated_at, datetime.datetime)

    stored_entries = service.get_entries(dictionary_id=dictionary_id, active_only=False)
    assert len(stored_entries) == 1
    stored_entry = stored_entries[0]
    assert stored_entry["id"] == response.id
    assert stored_entry["pattern"] == "hello"
    assert stored_entry["replacement"] == "world"


@pytest.mark.asyncio
async def test_timed_effects_round_trip_through_entry_endpoints(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Timed Effects Dictionary", "Description")

    response = await chat_endpoints.add_dictionary_entry(
        dictionary_id,
        DictionaryEntryCreate(
            pattern="pulse",
            replacement="heart-rate",
            timed_effects={"sticky": 17, "cooldown": 8, "delay": 3},
        ),
        db=chacha_db,
    )

    assert response.timed_effects is not None
    assert response.timed_effects.sticky == 17
    assert response.timed_effects.cooldown == 8
    assert response.timed_effects.delay == 3

    entries_response = await chat_endpoints.list_dictionary_entries(
        dictionary_id,
        group=None,
        db=chacha_db,
    )
    assert entries_response.total == 1
    assert entries_response.entries[0].timed_effects is not None
    assert entries_response.entries[0].timed_effects.sticky == 17
    assert entries_response.entries[0].timed_effects.cooldown == 8
    assert entries_response.entries[0].timed_effects.delay == 3

    dictionary_response = await chat_endpoints.get_chat_dictionary(dictionary_id, db=chacha_db)
    assert len(dictionary_response.entries) == 1
    assert dictionary_response.entries[0].timed_effects is not None
    assert dictionary_response.entries[0].timed_effects.sticky == 17
    assert dictionary_response.entries[0].timed_effects.cooldown == 8
    assert dictionary_response.entries[0].timed_effects.delay == 3


@pytest.mark.asyncio
async def test_case_sensitive_defaults_and_explicit_override_compatibility(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Case Sensitivity Dictionary", "Description")

    default_entry = await chat_endpoints.add_dictionary_entry(
        dictionary_id,
        DictionaryEntryCreate(pattern="default-case", replacement="DEFAULT"),
        db=chacha_db,
    )
    explicit_entry = await chat_endpoints.add_dictionary_entry(
        dictionary_id,
        DictionaryEntryCreate(
            pattern="explicit-case",
            replacement="EXPLICIT",
            case_sensitive=False,
        ),
        db=chacha_db,
    )

    assert default_entry.case_sensitive is True
    assert explicit_entry.case_sensitive is False

    entries_response = await chat_endpoints.list_dictionary_entries(
        dictionary_id,
        group=None,
        db=chacha_db,
    )
    cases_by_pattern = {
        entry.pattern: entry.case_sensitive for entry in entries_response.entries
    }
    assert cases_by_pattern["default-case"] is True
    assert cases_by_pattern["explicit-case"] is False


@pytest.mark.asyncio
async def test_get_chat_dictionary_includes_entry_metadata(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Metadata Dictionary", "desc")
    service.add_entry(
        dictionary_id,
        pattern="foo",
        replacement="bar",
        probability=0.5,
        group="group-a",
    )

    response = await chat_endpoints.get_chat_dictionary(dictionary_id, db=chacha_db)

    assert response.id == dictionary_id
    assert response.entry_count == 1
    assert len(response.entries) == 1
    entry = response.entries[0]
    assert entry.pattern == "foo"
    assert entry.replacement == "bar"
    assert isinstance(entry.created_at, datetime.datetime)
    assert isinstance(entry.updated_at, datetime.datetime)


@pytest.mark.asyncio
async def test_update_dictionary_entry_returns_latest_state(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Update Dictionary", None)
    entry_id = service.add_entry(dictionary_id, pattern="key", replacement="value")

    response = await chat_endpoints.update_dictionary_entry(
        entry_id,
        DictionaryEntryUpdate(group="updated-group", enabled=False, case_sensitive=False),
        db=chacha_db,
    )

    assert response.id == entry_id
    assert response.dictionary_id == dictionary_id
    assert response.group == "updated-group"
    assert response.enabled is False
    assert response.case_sensitive is False
    assert isinstance(response.updated_at, datetime.datetime)


@pytest.mark.asyncio
async def test_update_dictionary_entry_rejects_unsafe_regex_pattern(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Regex Guard Dictionary", None)
    entry_id = service.add_entry(
        dictionary_id,
        pattern="hello.*",
        replacement="hi",
        type="regex",
    )

    with pytest.raises(HTTPException) as exc_info:
        await chat_endpoints.update_dictionary_entry(
            entry_id,
            DictionaryEntryUpdate(pattern="(.+)+"),
            db=chacha_db,
        )

    assert exc_info.value.status_code == 400
    detail = str(exc_info.value.detail).lower()
    assert "dangerous regex pattern" in detail


@pytest.mark.asyncio
async def test_bulk_dictionary_entry_operations_reports_partial_failures(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Bulk Dictionary", None)
    entry_a = service.add_entry(dictionary_id, pattern="a", replacement="A")
    entry_b = service.add_entry(dictionary_id, pattern="b", replacement="B")

    response = await chat_endpoints.bulk_dictionary_entry_operations(
        BulkEntryOperation(
            entry_ids=[entry_a, entry_b, 999999],
            operation="activate",
        ),
        db=chacha_db,
    )

    assert response.success is False
    assert response.affected_count == 2
    assert response.failed_ids == [999999]


@pytest.mark.asyncio
async def test_bulk_dictionary_entry_operations_sets_group(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Bulk Group Dictionary", None)
    entry_id = service.add_entry(dictionary_id, pattern="bp", replacement="blood pressure")

    response = await chat_endpoints.bulk_dictionary_entry_operations(
        BulkEntryOperation(
            entry_ids=[entry_id],
            operation="group",
            group_name="reviewed",
        ),
        db=chacha_db,
    )

    assert response.success is True
    assert response.affected_count == 1
    updated_entry = service.get_entry(entry_id, active_only=False)
    assert updated_entry is not None
    assert updated_entry.get("group") == "reviewed"


@pytest.mark.asyncio
async def test_reorder_dictionary_entries_updates_execution_order(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Reorder Dictionary", None)
    entry_a = service.add_entry(dictionary_id, pattern="a", replacement="A")
    entry_b = service.add_entry(dictionary_id, pattern="b", replacement="B")
    entry_c = service.add_entry(dictionary_id, pattern="c", replacement="C")

    response = await chat_endpoints.reorder_dictionary_entries(
        dictionary_id,
        DictionaryEntryReorderRequest(entry_ids=[entry_c, entry_a, entry_b]),
        db=chacha_db,
    )

    assert response.success is True
    assert response.affected_count == 3
    assert response.entry_ids == [entry_c, entry_a, entry_b]

    ordered_entries = service.get_entries(dictionary_id=dictionary_id, active_only=False)
    assert [int(entry["id"]) for entry in ordered_entries] == [entry_c, entry_a, entry_b]


@pytest.mark.asyncio
async def test_reorder_dictionary_entries_rejects_incomplete_entry_list(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Reorder Validation Dictionary", None)
    entry_a = service.add_entry(dictionary_id, pattern="left", replacement="right")
    _entry_b = service.add_entry(dictionary_id, pattern="up", replacement="down")

    with pytest.raises(HTTPException) as exc_info:
        await chat_endpoints.reorder_dictionary_entries(
            dictionary_id,
            DictionaryEntryReorderRequest(entry_ids=[entry_a]),
            db=chacha_db,
        )

    assert exc_info.value.status_code == 400
    assert "every dictionary entry exactly once" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_list_chat_dictionaries_counts_inactive_entries(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Inactive Dictionary", None)
    service.add_entry(dictionary_id, pattern="alpha", replacement="beta")
    service.update_dictionary(dictionary_id, is_active=False)

    response = await chat_endpoints.list_chat_dictionaries(include_inactive=True, db=chacha_db)

    # list_chat_dictionaries returns ChatDictionaryResponse models
    dictionaries = {d.id: d for d in response.dictionaries}
    assert dictionary_id in dictionaries
    dict_payload = dictionaries[dictionary_id]
    assert dict_payload.is_active is False
    assert dict_payload.entry_count == 1


@pytest.mark.asyncio
async def test_list_chat_dictionaries_includes_usage_summary(chacha_db: CharactersRAGDB):
    service = ChatDictionaryService(chacha_db)
    dictionary_a = service.create_dictionary("Dictionary A", None)
    dictionary_b = service.create_dictionary("Dictionary B", None)

    character_id = chacha_db.add_character_card({"name": "Dictionary Usage Character"})
    assert character_id is not None

    active_chat_id = chacha_db.add_conversation(
        {
            "character_id": int(character_id),
            "title": "Active Dictionary Chat",
            "state": "in-progress",
        }
    )
    resolved_chat_id = chacha_db.add_conversation(
        {
            "character_id": int(character_id),
            "title": "Resolved Dictionary Chat",
            "state": "resolved",
        }
    )

    assert active_chat_id is not None
    assert resolved_chat_id is not None

    chacha_db.upsert_conversation_settings(
        str(active_chat_id),
        {"chat_dictionary_ids": [dictionary_a, dictionary_b]},
    )
    chacha_db.upsert_conversation_settings(
        str(resolved_chat_id),
        {"chatDictionaryId": dictionary_a},
    )

    response = await chat_endpoints.list_chat_dictionaries(
        include_inactive=True,
        include_usage=True,
        db=chacha_db,
    )

    dictionaries = {d.id: d for d in response.dictionaries}
    dictionary_a_payload = dictionaries[dictionary_a]
    dictionary_b_payload = dictionaries[dictionary_b]

    assert dictionary_a_payload.used_by_chat_count == 2
    assert dictionary_a_payload.used_by_active_chat_count == 1
    assert len(dictionary_a_payload.used_by_chat_refs) >= 1

    assert dictionary_b_payload.used_by_chat_count == 1
    assert dictionary_b_payload.used_by_active_chat_count == 1


@pytest.mark.asyncio
async def test_list_chat_dictionaries_includes_processing_priority(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_b = service.create_dictionary("Beta Dictionary", None)
    dictionary_a = service.create_dictionary("Alpha Dictionary", None)
    dictionary_inactive = service.create_dictionary("Inactive Dictionary", None)
    service.update_dictionary(dictionary_inactive, is_active=False)

    response = await chat_endpoints.list_chat_dictionaries(
        include_inactive=True,
        include_usage=False,
        db=chacha_db,
    )
    dictionaries = {item.id: item for item in response.dictionaries}

    assert dictionaries[dictionary_a].processing_priority == 1
    assert dictionaries[dictionary_b].processing_priority == 2
    assert dictionaries[dictionary_inactive].processing_priority is None


@pytest.mark.asyncio
async def test_process_text_without_dictionary_id_uses_dictionary_priority_order(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_z = service.create_dictionary("Zeta Dictionary", None)
    dictionary_a = service.create_dictionary("Alpha Dictionary", None)

    # Alphabetical dictionary order should run Alpha before Zeta.
    service.add_entry(dictionary_a, pattern="token", replacement="A")
    service.add_entry(dictionary_z, pattern="A", replacement="Z")

    response = await chat_endpoints.process_text_with_dictionaries(
        ProcessTextRequest(
            text="token",
            max_iterations=1,
        ),
        db=chacha_db,
    )

    assert response.processed_text == "Z"
    assert response.replacements == 2


@pytest.mark.asyncio
async def test_create_and_update_dictionary_default_token_budget(
    chacha_db: CharactersRAGDB,
):
    created = await chat_endpoints.create_chat_dictionary(
        ChatDictionaryCreate(
            name="Default Budget Dictionary",
            description="with budget",
            default_token_budget=640,
        ),
        db=chacha_db,
    )
    assert created.default_token_budget == 640

    updated = await chat_endpoints.update_chat_dictionary(
        created.id,
        ChatDictionaryUpdate(default_token_budget=1200),
        db=chacha_db,
    )
    assert updated.default_token_budget == 1200

    cleared = await chat_endpoints.update_chat_dictionary(
        created.id,
        ChatDictionaryUpdate(default_token_budget=None),
        db=chacha_db,
    )
    assert cleared.default_token_budget is None


@pytest.mark.asyncio
async def test_process_text_uses_dictionary_default_token_budget_and_records_activity(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary(
        "Activity Dictionary",
        "tracks activity",
        default_token_budget=250,
    )
    entry_id = service.add_entry(dictionary_id, pattern="term", replacement="TERM")

    response = await chat_endpoints.process_text_with_dictionaries(
        ProcessTextRequest(
            text="term term",
            dictionary_id=dictionary_id,
            chat_id="chat-activity-01",
            max_iterations=2,
        ),
        db=chacha_db,
    )

    assert response.token_budget_used == 250
    assert response.replacements >= 1
    assert entry_id in response.entries_used

    activity = await chat_endpoints.list_dictionary_activity(
        dictionary_id,
        limit=10,
        offset=0,
        db=chacha_db,
    )
    assert activity.dictionary_id == dictionary_id
    assert activity.total >= 1
    assert len(activity.events) >= 1

    event = activity.events[0]
    assert event.dictionary_id == dictionary_id
    assert event.chat_id == "chat-activity-01"
    assert entry_id in event.entries_used
    assert event.replacements >= 1
    assert event.original_text_preview.startswith("term")
    assert event.processed_text_preview
    assert isinstance(event.created_at, datetime.datetime)


@pytest.mark.asyncio
async def test_process_text_without_dictionary_id_uses_min_active_default_token_budget(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_a = service.create_dictionary(
        "Alpha Token Budget",
        None,
        default_token_budget=500,
    )
    dictionary_b = service.create_dictionary(
        "Beta Token Budget",
        None,
        default_token_budget=200,
    )
    service.add_entry(dictionary_a, pattern="foo", replacement="bar")
    service.add_entry(dictionary_b, pattern="bar", replacement="baz")

    response = await chat_endpoints.process_text_with_dictionaries(
        ProcessTextRequest(
            text="foo",
            max_iterations=2,
        ),
        db=chacha_db,
    )

    assert response.token_budget_used == 200
    assert response.processed_text == "baz"
    assert response.replacements >= 2


@pytest.mark.asyncio
async def test_dictionary_statistics_exposes_expanded_stage1_fields(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Statistics Dictionary", "desc")
    service.add_entry(dictionary_id, pattern="hello", replacement="hi")
    service.add_entry(
        dictionary_id,
        pattern="pulse",
        replacement="heart-rate",
        probability=0.3,
        timed_effects={"sticky": 15, "cooldown": 0, "delay": 0},
        enabled=False,
    )

    initial_stats = await chat_endpoints.get_dictionary_statistics(dictionary_id, db=chacha_db)
    assert initial_stats.total_entries == 2
    assert initial_stats.enabled_entries == 1
    assert initial_stats.disabled_entries == 1
    assert initial_stats.probabilistic_entries == 1
    assert initial_stats.timed_effect_entries == 1
    assert initial_stats.zero_usage_entries == 2
    assert len(initial_stats.entry_usage) == 2
    assert initial_stats.pattern_conflict_count == 0
    assert initial_stats.pattern_conflicts == []
    assert isinstance(initial_stats.created_at, datetime.datetime)
    assert isinstance(initial_stats.updated_at, datetime.datetime)
    assert initial_stats.total_usage_count == 0
    assert initial_stats.last_used is None

    await chat_endpoints.process_text_with_dictionaries(
        ProcessTextRequest(
            text="hello there",
            dictionary_id=dictionary_id,
        ),
        db=chacha_db,
    )

    usage_stats = await chat_endpoints.get_dictionary_statistics(dictionary_id, db=chacha_db)
    assert usage_stats.total_usage_count >= 1
    assert usage_stats.last_used is not None
    assert isinstance(usage_stats.last_used, datetime.datetime)
    assert usage_stats.zero_usage_entries == 1
    assert len(usage_stats.entry_usage) == 2
    assert usage_stats.pattern_conflict_count == 0
    assert usage_stats.pattern_conflicts == []


@pytest.mark.asyncio
async def test_dictionary_entry_usage_counts_increment_after_processing(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Entry Usage Dictionary", "desc")
    entry_id = service.add_entry(dictionary_id, pattern="term", replacement="TERM")

    entries_before = await chat_endpoints.list_dictionary_entries(
        dictionary_id,
        group=None,
        db=chacha_db,
    )
    before_entry = next(entry for entry in entries_before.entries if entry.id == entry_id)
    assert before_entry.usage_count == 0
    assert before_entry.last_used_at is None

    await chat_endpoints.process_text_with_dictionaries(
        ProcessTextRequest(
            text="term term",
            dictionary_id=dictionary_id,
        ),
        db=chacha_db,
    )

    entries_after = await chat_endpoints.list_dictionary_entries(
        dictionary_id,
        group=None,
        db=chacha_db,
    )
    after_entry = next(entry for entry in entries_after.entries if entry.id == entry_id)
    assert after_entry.usage_count >= 1
    assert after_entry.last_used_at is not None


@pytest.mark.asyncio
async def test_dictionary_statistics_reports_pattern_conflicts(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Conflict Dictionary", "desc")
    service.add_entry(dictionary_id, pattern="KCl", replacement="potassium chloride")
    service.add_entry(dictionary_id, pattern="/KC.*/", replacement="kc-regex", type="regex")
    service.add_entry(dictionary_id, pattern="kcl", replacement="kcl-lower")

    stats = await chat_endpoints.get_dictionary_statistics(dictionary_id, db=chacha_db)

    assert stats.pattern_conflict_count >= 2
    assert len(stats.pattern_conflicts) >= 2

    conflict_types = {conflict.conflict_type for conflict in stats.pattern_conflicts}
    assert "literal-regex" in conflict_types
    assert "literal-literal" in conflict_types


@pytest.mark.asyncio
async def test_update_chat_dictionary_returns_409_on_version_conflict(
    chacha_db: CharactersRAGDB,
):
    service = ChatDictionaryService(chacha_db)
    dictionary_id = service.create_dictionary("Versioned Dictionary", "desc")
    baseline = service.get_dictionary(dictionary_id)
    assert baseline is not None
    assert int(baseline["version"]) == 1

    service.update_dictionary(dictionary_id, description="edited in another session")

    with pytest.raises(HTTPException) as exc_info:
        await chat_endpoints.update_chat_dictionary(
            dictionary_id,
            ChatDictionaryUpdate(name="Conflicting Update", version=1),
            db=chacha_db,
        )

    assert exc_info.value.status_code == 409
    detail = str(exc_info.value.detail).lower()
    assert "modified by another session" in detail
    assert "expected version 1" in detail
