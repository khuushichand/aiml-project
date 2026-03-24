from __future__ import annotations

import json

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError
from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.DB_Management.scope_context import scoped_context


@pytest.mark.unit
def test_data_tables_crud_lifecycle():
    db = MediaDatabase(db_path=":memory:", client_id="owner1")

    table = db.create_data_table(
        name="Test Table",
        prompt="Make a summary table",
        description="Unit test table",
        column_hints={"name": "hint"},
    )
    assert table["uuid"]

    fetched = db.get_data_table_by_uuid(table["uuid"])
    assert fetched
    assert fetched["name"] == "Test Table"
    assert fetched["column_hints_json"]

    columns = [
        {"name": "Name", "type": "text", "position": 0},
        {"name": "Score", "type": "number", "position": 1},
    ]
    assert db.insert_data_table_columns(table["id"], columns) == 2
    listed_columns = db.list_data_table_columns(table["id"])
    column_ids = [c["column_id"] for c in listed_columns]

    rows = [
        {"row_index": 0, "row_json": {column_ids[0]: "Alice", column_ids[1]: 95}},
        {"row_index": 1, "row_json": {column_ids[0]: "Bob", column_ids[1]: 87}},
        {"row_index": 2, "row_json": {column_ids[0]: "Cara", column_ids[1]: 91}},
    ]
    assert db.insert_data_table_rows(table["id"], rows) == 3

    sources = [
        {
            "source_type": "rag_query",
            "source_id": "q1",
            "title": "Query 1",
            "snapshot_json": {"chunks": [{"chunk_id": "c1"}]},
            "retrieval_params_json": {"top_k": 10},
        }
    ]
    assert db.insert_data_table_sources(table["id"], sources) == 1

    assert [c["name"] for c in listed_columns] == ["Name", "Score"]

    listed_rows = db.list_data_table_rows(table["id"], limit=2, offset=1)
    assert len(listed_rows) == 2
    assert listed_rows[0]["row_index"] == 1
    assert json.loads(listed_rows[0]["row_json"])[column_ids[0]] == "Bob"

    listed_sources = db.list_data_table_sources(table["id"])
    assert listed_sources[0]["source_type"] == "rag_query"

    updated = db.update_data_table(table["id"], status="ready", row_count=3)
    assert updated
    assert updated["status"] == "ready"
    assert updated["row_count"] == 3
    prompt_updated = db.update_data_table(table["id"], prompt="Updated prompt")
    assert prompt_updated
    assert prompt_updated["prompt"] == "Updated prompt"

    assert db.soft_delete_data_table(table["id"]) is True
    assert db.get_data_table(table["id"]) is None

    columns_all = db.list_data_table_columns(table["id"], include_deleted=True)
    assert columns_all and all(col["deleted"] == 1 for col in columns_all)

    rows_all = db.list_data_table_rows(table["id"], include_deleted=True)
    assert rows_all and all(row["deleted"] == 1 for row in rows_all)

    sources_all = db.list_data_table_sources(table["id"], include_deleted=True)
    assert sources_all and all(src["deleted"] == 1 for src in sources_all)


@pytest.mark.unit
def test_data_tables_owner_scope(tmp_path):
    db_path = tmp_path / "Media_DB_v2.db"
    db_owner1 = MediaDatabase(db_path=str(db_path), client_id="1")
    table1 = db_owner1.create_data_table(name="Owner1", prompt="p1")

    db_owner2 = MediaDatabase(db_path=str(db_path), client_id="2")
    table2 = db_owner2.create_data_table(name="Owner2", prompt="p2")

    owner1_tables = db_owner1.list_data_tables(owner_user_id=1)
    assert len(owner1_tables) == 1
    assert owner1_tables[0]["uuid"] == table1["uuid"]

    owner2_tables = db_owner2.list_data_tables(owner_user_id=2)
    assert len(owner2_tables) == 1
    assert owner2_tables[0]["uuid"] == table2["uuid"]

    with scoped_context(user_id=1, org_ids=[], team_ids=[], is_admin=False):
        scoped_tables = db_owner2.list_data_tables()
        assert len(scoped_tables) == 1
        assert scoped_tables[0]["uuid"] == table1["uuid"]

    with scoped_context(user_id=999, org_ids=[], team_ids=[], is_admin=True):
        admin_tables = db_owner2.list_data_tables()
        assert {t["uuid"] for t in admin_tables} >= {table1["uuid"], table2["uuid"]}


@pytest.mark.unit
def test_data_table_children_owner_scope(tmp_path):
    db_path = tmp_path / "Media_DB_v2.db"
    db_owner1 = MediaDatabase(db_path=str(db_path), client_id="1")
    table = db_owner1.create_data_table(name="Owner1 Table", prompt="p1")
    table_id = int(table["id"])

    db_owner1.insert_data_table_columns(
        table_id,
        [{"name": "Name", "type": "text", "position": 0}],
    )
    column_id = db_owner1.list_data_table_columns(table_id)[0]["column_id"]
    db_owner1.insert_data_table_rows(
        table_id,
        [{"row_index": 0, "row_json": {column_id: "Alice"}}],
    )
    db_owner1.insert_data_table_sources(
        table_id,
        [{"source_type": "rag_query", "source_id": "q1"}],
    )

    db_owner2 = MediaDatabase(db_path=str(db_path), client_id="2")
    assert db_owner2.list_data_table_columns(table_id, owner_user_id=2) == []
    assert db_owner2.list_data_table_rows(table_id, owner_user_id=2) == []
    assert db_owner2.list_data_table_sources(table_id, owner_user_id=2) == []

    assert db_owner2.update_data_table(table_id, status="ready", owner_user_id=2) is None
    assert db_owner2.soft_delete_data_table(table_id, owner_user_id=2) is False
    assert db_owner1.get_data_table(table_id, owner_user_id=1) is not None


@pytest.mark.unit
def test_data_table_row_json_key_validation():
    db = MediaDatabase(db_path=":memory:", client_id="owner1")
    table = db.create_data_table(name="Keyed Table", prompt="p")
    table_id = int(table["id"])
    db.insert_data_table_columns(
        table_id,
        [
            {"name": "Name", "type": "text", "position": 0},
            {"name": "Score", "type": "number", "position": 1},
        ],
    )
    columns = db.list_data_table_columns(table_id)
    column_ids = [col["column_id"] for col in columns]
    with pytest.raises(InputError):
        db.insert_data_table_rows(
            table_id,
            [{"row_index": 0, "row_json": {column_ids[0]: "Alice", "unknown": 1}}],
        )


@pytest.mark.unit
def test_data_table_admin_updates_do_not_reassign_owner(tmp_path):
    db_path = tmp_path / "Media_DB_v2.db"
    owner_db = MediaDatabase(db_path=str(db_path), client_id="1")
    table = owner_db.create_data_table(name="Owner Table", prompt="p1", owner_user_id=1)
    table_id = int(table["id"])

    admin_db = MediaDatabase(db_path=str(db_path), client_id="admin")
    updated = admin_db.update_data_table(table_id, status="queued", owner_user_id=None)
    assert updated is not None
    assert updated["client_id"] == "1"

    admin_db.persist_data_table_generation(
        table_id,
        columns=[{"column_id": "col_1", "name": "Name", "type": "text", "position": 0}],
        rows=[{"row_id": "row_1", "row_index": 0, "row_json": {"col_1": "Alice"}}],
        sources=[{"source_type": "chat", "source_id": "chat_1"}],
        status="ready",
        row_count=1,
        owner_user_id=None,
    )

    assert owner_db.get_data_table(table_id, owner_user_id=1) is not None
    assert admin_db.get_data_table(table_id, owner_user_id="admin") is None
    assert len(owner_db.list_data_table_columns(table_id, owner_user_id=1)) == 1
    assert len(owner_db.list_data_table_rows(table_id, owner_user_id=1)) == 1
    assert len(owner_db.list_data_table_sources(table_id, owner_user_id=1)) == 1


@pytest.mark.unit
def test_replace_data_table_contents_replaces_columns_rows_and_preserves_sources():
    db = MediaDatabase(db_path=":memory:", client_id="1")
    table = db.create_data_table(name="Replace Table", prompt="p")
    table_id = int(table["id"])

    db.insert_data_table_columns(
        table_id,
        [{"name": "Name", "type": "text", "position": 0}],
    )
    old_column_id = db.list_data_table_columns(table_id)[0]["column_id"]
    db.insert_data_table_rows(
        table_id,
        [{"row_index": 0, "row_json": {old_column_id: "Alice"}}],
    )
    db.insert_data_table_sources(
        table_id,
        [{"source_type": "chat", "source_id": "chat_1"}],
    )

    column_count, row_count = db.replace_data_table_contents(
        table_id,
        owner_user_id="1",
        columns=[
            {"column_id": "col_replaced", "name": "Full Name", "type": "text", "position": 0},
            {"column_id": "col_score", "name": "Score", "type": "number", "position": 1},
        ],
        rows=[
            {"row_id": "row_replaced", "row_index": 0, "row_json": {"col_replaced": "Bob", "col_score": 98}},
        ],
    )

    assert (column_count, row_count) == (2, 1)

    active_columns = db.list_data_table_columns(table_id)
    assert [column["column_id"] for column in active_columns] == ["col_replaced", "col_score"]

    active_rows = db.list_data_table_rows(table_id)
    assert len(active_rows) == 1
    assert active_rows[0]["row_id"] == "row_replaced"
    assert json.loads(active_rows[0]["row_json"]) == {"col_replaced": "Bob", "col_score": 98}

    all_columns = db.list_data_table_columns(table_id, include_deleted=True)
    assert len(all_columns) == 3
    assert len([column for column in all_columns if column["deleted"] == 1]) == 1

    all_rows = db.list_data_table_rows(table_id, include_deleted=True)
    assert len(all_rows) == 2
    assert len([row for row in all_rows if row["deleted"] == 1]) == 1

    sources = db.list_data_table_sources(table_id)
    assert len(sources) == 1
    assert sources[0]["source_id"] == "chat_1"


@pytest.mark.unit
def test_update_data_table_can_clear_last_error():
    db = MediaDatabase(db_path=":memory:", client_id="1")
    table = db.create_data_table(name="Status Table", prompt="p")
    table_id = int(table["id"])

    failed = db.update_data_table(table_id, status="failed", last_error="boom", owner_user_id=1)
    assert failed is not None
    assert failed["last_error"] == "boom"

    cleared = db.update_data_table(table_id, status="running", last_error=None, owner_user_id=1)
    assert cleared is not None
    assert cleared["last_error"] is None
