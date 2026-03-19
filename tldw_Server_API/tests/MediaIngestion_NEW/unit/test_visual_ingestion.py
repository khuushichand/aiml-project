from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing import visual_ingestion


@pytest.mark.unit
def test_persist_visual_documents_from_analysis(tmp_path, monkeypatch):
    db_path = Path(tmp_path) / "media.db"
    db = MediaDatabase(db_path=str(db_path), client_id="tests-visual")
    media_id, _, _ = db.add_media_with_keywords(
        title="Visual Source",
        media_type="document",
        content="base content",
        keywords=[],
    )
    db.close_connection()

    monkeypatch.setenv("VISUAL_RAG_ENABLE", "1")
    monkeypatch.setenv("VISUAL_RAG_MAX_IMAGES_PER_MEDIA", "1")
    visual_ingestion._visual_rag_settings.cache_clear()
    events = []

    @contextlib.contextmanager
    def _fake_managed_media_database(client_id, **kwargs):
        events.append(("open", client_id, kwargs))
        helper_db = MediaDatabase(db_path=str(db_path), client_id=client_id)
        try:
            yield helper_db
        finally:
            helper_db.close_connection()

    monkeypatch.setattr(
        visual_ingestion,
        "MediaDatabase",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("visual_ingestion should not construct MediaDatabase directly")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        visual_ingestion,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )

    analysis_details = {
        "vlm": {
            "by_page": [
                {
                    "page": 1,
                    "detections": [
                        {"label": "table", "score": 0.9, "bbox": [0.0, 0.0, 1.0, 1.0]}
                    ],
                }
            ]
        }
    }

    created = visual_ingestion.persist_visual_documents_from_analysis(
        db_path=str(db_path),
        client_id="tests-visual",
        media_id=int(media_id),
        analysis_details=analysis_details,
    )

    assert created == 1
    assert events == [
        (
            "open",
            "tests-visual",
            {
                "db_path": str(db_path),
                "initialize": False,
            },
        )
    ]

    db_verify = MediaDatabase(db_path=str(db_path), client_id="tests-visual")
    docs = db_verify.list_visual_documents_for_media(media_id)
    db_verify.close_connection()

    assert len(docs) == 1
    assert docs[0]["caption"].lower().startswith("detected")
