import pytest

from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import (
    RetrievalConfig,
    SQLRetriever,
)
from tldw_Server_API.app.core.RAG.rag_service.types import DataSource


class _ServiceShouldNotRun:
    async def generate_and_execute(self, **kwargs):
        _ = kwargs
        raise AssertionError("service should not be called for non-sql input")


class _StubService:
    def __init__(self):
        self.calls = 0

    async def generate_and_execute(self, **kwargs):
        self.calls += 1
        _ = kwargs
        return {
            "sql": "SELECT id FROM media LIMIT 1",
            "columns": ["id"],
            "rows": [{"id": 1}],
            "row_count": 1,
            "guardrail": {"limit_injected": False, "limit_clamped": False},
            "truncated": False,
        }


@pytest.mark.asyncio
async def test_sql_retriever_rejects_non_sql_input_and_records_telemetry(monkeypatch):
    counters = []
    durations = []

    def _capture_counter(self, outcome, reason=None):
        counters.append((outcome, reason))

    def _capture_duration(self, duration_seconds, outcome):
        durations.append((outcome, duration_seconds))

    monkeypatch.setattr(SQLRetriever, "_emit_counter", _capture_counter, raising=False)
    monkeypatch.setattr(SQLRetriever, "_emit_duration", _capture_duration, raising=False)

    retriever = SQLRetriever(
        db_path=":memory:",
        config=RetrievalConfig(max_results=5),
        service=_ServiceShouldNotRun(),
    )

    docs = await retriever.retrieve("show me the latest media rows")

    assert docs == []
    assert counters == [("non_sql_input", None)]
    assert durations
    assert durations[0][0] == "non_sql_input"


@pytest.mark.asyncio
async def test_sql_retriever_records_success_telemetry_for_sql_input(monkeypatch):
    counters = []
    durations = []
    rows = []

    def _capture_counter(self, outcome, reason=None):
        counters.append((outcome, reason))

    def _capture_duration(self, duration_seconds, outcome):
        durations.append((outcome, duration_seconds))

    def _capture_rows(self, row_count, outcome):
        rows.append((outcome, row_count))

    monkeypatch.setattr(SQLRetriever, "_emit_counter", _capture_counter, raising=False)
    monkeypatch.setattr(SQLRetriever, "_emit_duration", _capture_duration, raising=False)
    monkeypatch.setattr(SQLRetriever, "_emit_rows", _capture_rows, raising=False)

    service = _StubService()
    retriever = SQLRetriever(
        db_path=":memory:",
        config=RetrievalConfig(max_results=5),
        service=service,
    )

    docs = await retriever.retrieve("SELECT id FROM media LIMIT 1")

    assert service.calls == 1
    assert len(docs) == 1
    assert docs[0].source == DataSource.SQL
    assert counters and counters[-1][0] == "success"
    assert durations and durations[-1][0] == "success"
    assert rows == [("success", 1)]
