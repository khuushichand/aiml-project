import json

import pytest

from tldw_Server_API.app.api.v1.schemas.data_tables_schemas import DATA_TABLES_MAX_ROWS_LIMIT
from tldw_Server_API.app.core.Data_Tables import jobs_worker
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.unit


class _StubAdapter:
    def __init__(self, payload):
        self._payload = payload

    def chat(self, _request):
        return {"choices": [{"message": {"content": json.dumps(self._payload)}}]}


@pytest.mark.asyncio
async def test_data_tables_worker_generates_rows(monkeypatch, tmp_path):
    media_path = tmp_path / "media.db"
    chacha_path = tmp_path / "chacha.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setattr(jobs_worker, "get_user_media_db_path", lambda _user_id: str(media_path))
    monkeypatch.setattr(jobs_worker, "get_user_chacha_db_path", lambda _user_id: str(chacha_path))

    db = MediaDatabase(db_path=str(media_path), client_id="1")
    table = db.create_data_table(
        name="Worker Table",
        prompt="Summarize chunks",
        description="unit",
        status="queued",
        row_count=0,
    )
    table_id = int(table.get("id"))

    snapshot = {
        "query": "summarize",
        "retrieval": {"sources": ["media_db"]},
        "chunks": [
            {
                "chunk_id": "chunk_1",
                "chunk_text": "alpha beta gamma",
                "score": 0.9,
                "rank": 1,
            }
        ],
    }

    llm_payload = {
        "columns": [
            {"name": "Term", "type": "text"},
            {"name": "Count", "type": "number"},
        ],
        "rows": [
            ["alpha", 1],
            ["beta", 2],
        ],
    }

    monkeypatch.setattr(jobs_worker, "_get_adapter", lambda _provider: _StubAdapter(llm_payload))
    monkeypatch.setattr(jobs_worker, "_resolve_model", lambda *_args, **_kwargs: "test-model")
    monkeypatch.setattr(jobs_worker, "provider_requires_api_key", lambda _p: False)
    monkeypatch.setattr(jobs_worker, "resolve_provider_api_key", lambda *_a, **_k: ("", {}))
    monkeypatch.setattr(jobs_worker, "DEFAULT_LLM_PROVIDER", "openai")
    monkeypatch.setattr(jobs_worker, "load_and_log_configs", lambda: {})

    job = {
        "id": 1,
        "job_type": "data_table_generate",
        "owner_user_id": "1",
        "payload": {
            "table_id": table_id,
            "table_uuid": table.get("uuid"),
            "prompt": "Summarize chunks",
            "sources": [
                {
                    "source_type": "rag_query",
                    "source_id": "summarize",
                    "snapshot": snapshot,
                }
            ],
            "max_rows": 5,
        },
    }

    jm = JobManager()
    result = await jobs_worker._handle_job(job, jm)
    assert result["row_count"] == 2

    refreshed = db.get_data_table(table_id, include_deleted=True)
    assert refreshed["status"] == "ready"
    assert refreshed["row_count"] == 2

    columns = db.list_data_table_columns(table_id)
    rows = db.list_data_table_rows(table_id, limit=10, offset=0)
    assert len(columns) == 2
    assert len(rows) == 2

    row_json = json.loads(rows[0]["row_json"])
    assert set(row_json.keys()) == {columns[0]["column_id"], columns[1]["column_id"]}


def test_dedupe_column_names_is_case_insensitive():
    deduped = jobs_worker._dedupe_column_names(["Name", "name", "NAME"])
    assert deduped == ["Name", "name (2)", "NAME (3)"]


def test_worker_max_rows_limit_matches_api_schema_limit():
    assert jobs_worker._MAX_ROWS_LIMIT == DATA_TABLES_MAX_ROWS_LIMIT
