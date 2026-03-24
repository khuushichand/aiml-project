import sqlite3
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


pytestmark = pytest.mark.unit


class _FakeMediaAuxDb:
    def __init__(self, *, keywords: list[str] | None = None, media_exists: bool = True):
        self._keywords = keywords or []
        self._media_exists = media_exists
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def fetch_all_keywords(self) -> list[str]:
        return list(self._keywords)

    def get_media_by_id(self, media_id: int, include_deleted: bool = False, include_trash: bool = False):
        if not self._media_exists:
            return None
        return {
            "id": media_id,
            "title": f"Media {media_id}",
            "type": "document",
            "deleted": int(include_deleted),
            "is_trash": int(include_trash),
        }

    @contextmanager
    def transaction(self):
        try:
            yield self._conn
            self._conn.commit()
        finally:
            pass

    def close(self) -> None:
        self._conn.close()


@pytest.fixture
def media_auxiliary_client():
    from tldw_Server_API.app.api.v1.endpoints.media.listing import router as listing_router
    from tldw_Server_API.app.api.v1.endpoints.media.reading_progress import router as reading_progress_router

    app = FastAPI()
    app.include_router(listing_router, prefix="/api/v1/media", tags=["media"])
    app.include_router(reading_progress_router, prefix="/api/v1/media", tags=["media"])
    db = _FakeMediaAuxDb(keywords=["alpha", "beta", "almanac"])
    app.dependency_overrides[get_media_db_for_user] = lambda: db
    app.dependency_overrides[get_request_user] = lambda: type("User", (), {"id": 1})()
    with TestClient(app) as client:
        yield client, db
    db.close()


def test_media_keywords_endpoint_returns_filtered_keywords(media_auxiliary_client):
    client, _db = media_auxiliary_client

    response = client.get("/api/v1/media/keywords", params={"query": "al"})

    assert response.status_code == 200, response.text  # nosec B101
    assert response.json() == {"keywords": ["alpha", "almanac"]}  # nosec B101


def test_reading_progress_returns_no_progress_payload_instead_of_500(media_auxiliary_client):
    client, _db = media_auxiliary_client

    response = client.get("/api/v1/media/42/progress")

    assert response.status_code == 200, response.text  # nosec B101
    assert response.json() == {"media_id": 42, "has_progress": False}  # nosec B101


def test_reading_progress_treats_corrupt_rows_as_missing_progress(media_auxiliary_client):
    client, db = media_auxiliary_client

    with db.transaction() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_reading_progress (
                media_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                current_page INTEGER NOT NULL DEFAULT 1,
                total_pages INTEGER NOT NULL DEFAULT 1,
                zoom_level INTEGER NOT NULL DEFAULT 100,
                view_mode TEXT NOT NULL DEFAULT 'single',
                cfi TEXT,
                percentage REAL,
                last_read_at TEXT NOT NULL,
                PRIMARY KEY (media_id, user_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO document_reading_progress
            (media_id, user_id, current_page, total_pages, zoom_level, view_mode, cfi, percentage, last_read_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (99, "1", 3, 10, 100, "broken-mode", None, None, "not-a-timestamp"),
        )

    response = client.get("/api/v1/media/99/progress")

    assert response.status_code == 200, response.text  # nosec B101
    assert response.json() == {"media_id": 99, "has_progress": False}  # nosec B101
