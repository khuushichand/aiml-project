from tldw_Server_API.app.core.DB_Management.backends.base import QueryResult
from tldw_Server_API.app.core.DB_Management.media_db.runtime.rows import (
    BackendCursorAdapter,
    RowAdapter,
)


def test_row_adapter_supports_index_and_key_access() -> None:
    row = RowAdapter({"id": 7, "title": "Doc"}, [("id",), ("title",)])

    assert row[0] == 7
    assert row["title"] == "Doc"


def test_backend_cursor_adapter_wraps_query_results() -> None:
    adapter = BackendCursorAdapter(
        QueryResult(
            rows=[{"id": 1, "title": "First"}, {"id": 2, "title": "Second"}],
            rowcount=2,
            description=[("id",), ("title",)],
        )
    )

    first = adapter.fetchone()
    remaining = adapter.fetchall()

    assert first[0] == 1
    assert first["title"] == "First"
    assert remaining[0]["title"] == "First"
    assert remaining[1]["title"] == "Second"
