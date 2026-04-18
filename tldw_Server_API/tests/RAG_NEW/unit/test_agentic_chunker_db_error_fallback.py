from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError
from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import AgenticConfig, AgenticToolbox
from tldw_Server_API.app.core.RAG.rag_service.types import DataSource, Document


def _expect_true(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


class _BrokenStructureDb:
    def lookup_section_by_heading(self, media_id: int, heading: str) -> Any:
        raise DatabaseError("structure lookup failed")


def test_open_section_falls_back_to_heuristics_on_database_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "tldw_Server_API.app.core.RAG.rag_service.agentic_chunker._get_media_db_for_structure",
        lambda: _BrokenStructureDb(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.config.rag_enable_structure_index",
        lambda: True,
    )

    doc = Document(
        id="doc-1",
        content="# Methods\nIntro.\n\n# Results\nTable content lives here.\n",
        metadata={
            "title": "Paper",
            "source": "media_db",
            "ingestion_date": "2024-01-01",
            "media_id": 7,
        },
        source=DataSource.MEDIA_DB,
        score=0.9,
    )
    toolbox = AgenticToolbox([doc], AgenticConfig(enable_section_index=True))

    result = toolbox.open_section(doc, "Results")

    _expect_true(isinstance(result, tuple), f"expected heuristic fallback tuple, got {result!r}")
    _expect_true(result[0] < result[1], f"expected valid section span, got {result!r}")
