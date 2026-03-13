import json
import uuid
import io
import zipfile
import sqlite3
import os
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from loguru import logger

# Keep this module self-contained and deterministic by disabling optional
# reading-digest startup paths that pull heavyweight STT deps during app import.
os.environ.setdefault("READING_DIGEST_JOBS_WORKER_ENABLED", "0")
os.environ.setdefault("READING_DIGEST_SCHEDULER_ENABLED", "0")
os.environ.setdefault("TEST_MODE", "1")

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Flashcards.apkg_exporter import export_apkg_from_rows
from tldw_Server_API.tests.test_config import TestConfig

# Explicit auth headers for single-user mode (required by get_request_user)
AUTH_HEADERS = {"X-API-KEY": TestConfig.TEST_API_KEY}


@pytest.fixture(scope="function")
def flashcards_db(tmp_path):
    db_path = tmp_path / "flashcards.db"
    db = CharactersRAGDB(str(db_path), client_id=f"test-{uuid.uuid4().hex[:6]}")
    yield db
    db.close_connection()


@pytest.fixture
def client_with_flashcards_db(flashcards_db: CharactersRAGDB):
    TestConfig.setup_test_environment()
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
    def override_get_db():
        logger.info("[TEST] override get_chacha_db_for_user -> flashcards_db")
        try:
            yield flashcards_db
        finally:
            pass
    # Also bypass AuthNZ in tests by returning a fixed user
    async def override_user():
        # Use an admin-capable user so tests can exercise admin-only query caps
        return User(
            id=1,
            username="testuser",
            email="test@example.com",
            is_active=True,
            roles=["admin"],
            is_admin=True,
        )

    # Apply dependency overrides
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    fastapi_app.dependency_overrides[get_request_user] = override_user

    # Provide a TestClient with default X-API-KEY header for all requests
    default_headers = {"X-API-KEY": TestConfig.TEST_API_KEY}
    with TestClient(fastapi_app, headers=default_headers) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
    TestConfig.reset_settings()


def test_export_apkg_basic_integration(client_with_flashcards_db: TestClient):
    # Create deck
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckOne", "description": "d1"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    deck = r.json()
    deck_id = deck["id"]

    # Create basic card
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "What is 2+2?",
        "back": "4",
        "tags": ["math"]
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200

    # Create reverse card
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "USA capital?",
        "back": "Washington, D.C.",
        "model_type": "basic_reverse"
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200

    # Create cloze card with two clozes and embedded data URI image in Extra
    img_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    extra_html = f"<img src='data:image/png;base64,{img_b64}'/>"
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "The capital of {{c1::France}} is {{c2::Paris}}.",
        "back": "",
        "model_type": "cloze",
        "extra": extra_html,
        "tags": ["geo"]
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200

    # Export APKG
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/apkg")
    apkg = r.content
    # open and verify
    zf = zipfile.ZipFile(io.BytesIO(apkg))
    try:
        assert 'collection.anki2' in zf.namelist()
        media_json = zf.read('media').decode('utf-8')
        media_map = json.loads(media_json)
        # At least one media from cloze extra
        assert len(media_map) >= 1
        first_index = sorted(media_map.keys())[0]
        assert first_index in zf.namelist()

        # Load notes/cards to check counts
        with zf.open('collection.anki2') as f:
            data = f.read()
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'col.anki2')
            with open(p, 'wb') as fh:
                fh.write(data)
            conn = sqlite3.connect(p)
            try:
                notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
                cards = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
                # 3 notes: basic, reverse, cloze
                assert notes == 3
                # Cards: basic=1, basic_reverse=2, cloze with c1,c2 adds 2 => total 5
                assert cards == 5
            finally:
                conn.close()
    finally:
        zf.close()


def test_generate_flashcards_endpoint_returns_generated_cards(
    client_with_flashcards_db: TestClient,
    monkeypatch,
):
    async def fake_generate_adapter(config, context):
        assert config.get("text") == "Cell respiration summary"
        assert config.get("num_cards") == 2
        return {
            "flashcards": [
                {"front": "ATP stands for?", "back": "Adenosine triphosphate", "tags": ["bio"]},
                {"front": "Where does glycolysis occur?", "back": "Cytoplasm", "tags": "biology metabolism"},
            ],
            "count": 2,
        }

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.flashcards.run_flashcard_generate_adapter",
        fake_generate_adapter,
    )

    response = client_with_flashcards_db.post(
        "/api/v1/flashcards/generate",
        json={
            "text": "Cell respiration summary",
            "num_cards": 2,
            "card_type": "basic",
            "difficulty": "medium",
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["flashcards"][0]["front"] == "ATP stands for?"
    assert payload["flashcards"][1]["tags"] == ["biology", "metabolism"]


def test_export_apkg_include_reverse_flag_generates_reverse(client_with_flashcards_db: TestClient):
    # Create deck and a plain basic card (no reverse/model_type)
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckTwo"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Capital of Japan?",
        "back": "Tokyo"
    }, headers=AUTH_HEADERS)
    card = r.json()
    assert card["model_type"] == "basic"
    assert card["reverse"] is False

    # Export with include_reverse=true
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg", "include_reverse": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    try:
        with zf.open('collection.anki2') as f:
            data = f.read()
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'col.anki2')
            with open(p, 'wb') as fh:
                fh.write(data)
            conn = sqlite3.connect(p)
            try:
                # There should be two cards for the single basic note
                notes = conn.execute("SELECT id FROM notes").fetchall()
                assert len(notes) == 1
                nid = notes[0][0]
                cards = conn.execute("SELECT nid, ord FROM cards").fetchall()
                assert len(cards) == 2
                assert all(c[0] == nid for c in cards)
                ords = sorted(c[1] for c in cards)
                assert ords == [0, 1]
            finally:
                conn.close()
    finally:
        zf.close()


def test_export_apkg_basic_reverse_without_include_reverse(client_with_flashcards_db: TestClient):
    # Create deck and a basic_reverse card (no include_reverse flag)
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckBasicRev"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Front BR",
        "back": "Back BR",
        "model_type": "basic_reverse"
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200

    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    try:
        with zf.open('collection.anki2') as f:
            data = f.read()
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'col.anki2')
            with open(p, 'wb') as fh:
                fh.write(data)
            conn = sqlite3.connect(p)
            try:
                notes = conn.execute("SELECT id FROM notes").fetchall()
                assert len(notes) == 1
                nid = notes[0][0]
                cards = conn.execute("SELECT nid, ord FROM cards").fetchall()
                assert len(cards) == 2
                assert all(c[0] == nid for c in cards)
                assert sorted(c[1] for c in cards) == [0, 1]
            finally:
                conn.close()
    finally:
        zf.close()


def test_export_csv_shape_and_content(client_with_flashcards_db: TestClient):
    # Create deck and two cards with tags and notes
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "CSVDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Q1",
        "back": "A1",
        "notes": "N1",
        "tags": ["alpha", "beta"]
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Q2",
        "back": "A2",
        "notes": "N2",
        "tags": ["gamma"]
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200

    # Export CSV (TSV)
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", headers=AUTH_HEADERS)
    assert r.status_code == 200
    text = r.content.decode('utf-8')
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 2
    for ln in lines:
        cols = ln.split('\t')
        # Expect 5 columns: Deck, Front, Back, Tags, Notes
        assert len(cols) == 5
        assert cols[0] == "CSVDeck"
    # Verify tags and notes appear for first card
    assert any("alpha beta" in ln and "N1" in ln for ln in lines)
    assert any("gamma" in ln and "N2" in ln for ln in lines)


def test_set_tags_and_linkage(client_with_flashcards_db: TestClient):
    # Create deck and a card
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "TagDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Tagged Q",
        "back": "Tagged A"
    }, headers=AUTH_HEADERS)
    card = r.json()
    uuid = card["uuid"]

    # Set tags via endpoint
    r = client_with_flashcards_db.put(f"/api/v1/flashcards/{uuid}/tags", json={"tags": ["alpha", "beta"]}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    updated = r.json()
    assert updated.get("tags") == ["alpha", "beta"]
    # tags_json returns JSON string
    tags_json = updated.get("tags_json")
    assert tags_json
    tags = json.loads(tags_json)
    assert set(tags) == {"alpha", "beta"}

    # Verify keyword linkage
    r = client_with_flashcards_db.get(f"/api/v1/flashcards/{uuid}/tags", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    items = data.get("items", [])
    kw_texts = {kw.get("keyword") for kw in items}
    assert {"alpha", "beta"}.issubset(kw_texts)


def test_get_flashcard_alias_path_returns_card(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "AliasDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Alias Q",
        "back": "Alias A",
        "tags": ["t1"]
    }, headers=AUTH_HEADERS)
    card = r.json()
    uuid = card["uuid"]

    r = client_with_flashcards_db.get(f"/api/v1/flashcards/{uuid}", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["uuid"] == uuid
    assert data.get("tags") == ["t1"]


def test_source_attribution_fields_present_in_flashcard_responses(client_with_flashcards_db: TestClient):
    deck_response = client_with_flashcards_db.post(
        "/api/v1/flashcards/decks",
        json={"name": "SourceDeck"},
        headers=AUTH_HEADERS,
    )
    assert deck_response.status_code == 200
    deck_id = deck_response.json()["id"]

    created_response = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={
            "deck_id": deck_id,
            "front": "Source Q",
            "back": "Source A",
            "source_ref_type": "media",
            "source_ref_id": "42",
        },
        headers=AUTH_HEADERS,
    )
    assert created_response.status_code == 200
    created = created_response.json()
    card_uuid = created["uuid"]

    assert created["source_ref_type"] == "media"
    assert created["source_ref_id"] == "42"
    assert "conversation_id" in created
    assert "message_id" in created
    assert created["conversation_id"] is None
    assert created["message_id"] is None

    list_response = client_with_flashcards_db.get("/api/v1/flashcards", headers=AUTH_HEADERS)
    assert list_response.status_code == 200
    listed_items = list_response.json().get("items", [])
    listed = next((item for item in listed_items if item.get("uuid") == card_uuid), None)
    assert listed is not None
    assert listed["source_ref_type"] == "media"
    assert listed["source_ref_id"] == "42"
    assert "conversation_id" in listed
    assert "message_id" in listed

    get_response = client_with_flashcards_db.get(f"/api/v1/flashcards/{card_uuid}", headers=AUTH_HEADERS)
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["source_ref_type"] == "media"
    assert fetched["source_ref_id"] == "42"
    assert "conversation_id" in fetched
    assert "message_id" in fetched


def test_openapi_flashcard_response_includes_source_fields():
    openapi = fastapi_app.openapi()
    flashcard_schema = openapi["components"]["schemas"]["Flashcard"]
    properties = flashcard_schema.get("properties", {})

    assert "source_ref_type" in properties
    assert "source_ref_id" in properties
    assert "conversation_id" in properties
    assert "message_id" in properties


def test_create_flashcard_normalizes_model_fields(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "NormalizeDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Cloze {{c1::x}}",
        "back": "",
        "is_cloze": True
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200
    card = r.json()
    assert card["model_type"] == "cloze"
    assert card["is_cloze"] is True
    assert card["reverse"] is False


def test_bulk_create_rejects_invalid_cloze(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "BulkDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards/bulk", json=[{
        "deck_id": deck_id,
        "front": "No cloze pattern here",
        "back": "",
        "model_type": "cloze"
    }], headers=AUTH_HEADERS)
    assert r.status_code == 400


def test_review_missing_flashcard_returns_404(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/review", json={
        "card_uuid": str(uuid.uuid4()),
        "rating": 3
    }, headers=AUTH_HEADERS)
    assert r.status_code == 404


def test_analytics_summary_returns_daily_metrics_and_deck_progress(client_with_flashcards_db: TestClient):
    # Seed one deck and two cards
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/decks",
        json={"name": "AnalyticsDeck"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    deck_id = r.json()["id"]

    first = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={"deck_id": deck_id, "front": "Q1", "back": "A1"},
        headers=AUTH_HEADERS,
    )
    second = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={"deck_id": deck_id, "front": "Q2", "back": "A2"},
        headers=AUTH_HEADERS,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    first_uuid = first.json()["uuid"]
    second_uuid = second.json()["uuid"]

    # One successful recall + one lapse to verify retention/lapse calculations
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/review",
        json={"card_uuid": first_uuid, "rating": 3, "answer_time_ms": 2500},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/review",
        json={"card_uuid": second_uuid, "rating": 1, "answer_time_ms": 4500},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200

    # Fetch analytics summary
    r = client_with_flashcards_db.get("/api/v1/flashcards/analytics/summary", headers=AUTH_HEADERS)
    assert r.status_code == 200
    payload = r.json()

    assert payload["reviewed_today"] == 2
    assert payload["study_streak_days"] >= 1
    assert payload["avg_answer_time_ms_today"] == pytest.approx(3500.0)
    assert payload["retention_rate_today"] == pytest.approx(50.0)
    assert payload["lapse_rate_today"] == pytest.approx(50.0)
    assert payload.get("generated_at")

    deck = next((d for d in payload["decks"] if d["deck_id"] == deck_id), None)
    assert deck is not None
    assert deck["deck_name"] == "AnalyticsDeck"
    assert deck["total"] == 2
    assert deck["new"] == 0


def test_analytics_summary_honors_deck_filter(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/decks",
        json={"name": "DeckA"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    deck_a = r.json()["id"]

    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/decks",
        json={"name": "DeckB"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    deck_b = r.json()["id"]

    card_a = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={"deck_id": deck_a, "front": "A1", "back": "A1"},
        headers=AUTH_HEADERS,
    )
    card_b = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={"deck_id": deck_b, "front": "B1", "back": "B1"},
        headers=AUTH_HEADERS,
    )
    assert card_a.status_code == 200
    assert card_b.status_code == 200

    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/review",
        json={"card_uuid": card_a.json()["uuid"], "rating": 3, "answer_time_ms": 1200},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/review",
        json={"card_uuid": card_b.json()["uuid"], "rating": 1, "answer_time_ms": 3600},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200

    scoped = client_with_flashcards_db.get(
        "/api/v1/flashcards/analytics/summary",
        params={"deck_id": deck_a},
        headers=AUTH_HEADERS,
    )
    assert scoped.status_code == 200
    payload = scoped.json()

    assert payload["reviewed_today"] == 1
    assert payload["avg_answer_time_ms_today"] == pytest.approx(1200.0)
    assert payload["retention_rate_today"] == pytest.approx(100.0)
    assert payload["lapse_rate_today"] == pytest.approx(0.0)
    assert len(payload["decks"]) == 1
    assert payload["decks"][0]["deck_id"] == deck_a
    assert payload["decks"][0]["deck_name"] == "DeckA"


def test_reset_scheduling_resets_card_to_new_defaults(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/decks",
        json={"name": "ResetDeck"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    deck_id = r.json()["id"]

    created = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={"deck_id": deck_id, "front": "Reset Q", "back": "Reset A"},
        headers=AUTH_HEADERS,
    )
    assert created.status_code == 200
    card = created.json()
    card_uuid = card["uuid"]

    reviewed = client_with_flashcards_db.post(
        "/api/v1/flashcards/review",
        json={"card_uuid": card_uuid, "rating": 3, "answer_time_ms": 2100},
        headers=AUTH_HEADERS,
    )
    assert reviewed.status_code == 200
    reviewed_payload = reviewed.json()
    assert reviewed_payload["repetitions"] >= 1

    current = client_with_flashcards_db.get(f"/api/v1/flashcards/id/{card_uuid}", headers=AUTH_HEADERS)
    assert current.status_code == 200
    current_version = current.json()["version"]

    reset = client_with_flashcards_db.post(
        f"/api/v1/flashcards/{card_uuid}/reset-scheduling",
        json={"expected_version": current_version},
        headers=AUTH_HEADERS,
    )
    assert reset.status_code == 200
    payload = reset.json()

    assert payload["ef"] == pytest.approx(2.5)
    assert payload["interval_days"] == 0
    assert payload["repetitions"] == 0
    assert payload["lapses"] == 0
    assert payload["last_reviewed_at"] is None
    assert payload["due_at"] is not None

    conflict = client_with_flashcards_db.post(
        f"/api/v1/flashcards/{card_uuid}/reset-scheduling",
        json={"expected_version": current_version},
        headers=AUTH_HEADERS,
    )
    assert conflict.status_code == 409


def test_patch_partial_update_keeps_required_fields(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "PatchDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Qpatch",
        "back": "Apatch",
        "notes": "N1",
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200
    uuid = r.json()["uuid"]

    r = client_with_flashcards_db.patch(f"/api/v1/flashcards/{uuid}", json={"notes": "N2"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    updated = r.json()
    assert updated["front"] == "Qpatch"
    assert updated["back"] == "Apatch"
    assert updated["notes"] == "N2"


def test_patch_tags_conflict_does_not_update(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "PatchTags"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Qtag",
        "back": "Atag",
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200
    card = r.json()
    uuid = card["uuid"]
    version = card["version"]

    r = client_with_flashcards_db.patch(
        f"/api/v1/flashcards/{uuid}",
        json={"tags": ["alpha"], "expected_version": version + 1},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 409

    r = client_with_flashcards_db.get(f"/api/v1/flashcards/{uuid}/tags", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json().get("count") == 0

    r = client_with_flashcards_db.get(f"/api/v1/flashcards/id/{uuid}", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json().get("tags_json") in (None, "[]")


def test_patch_deck_id_rejects_invalid_or_deleted(
    client_with_flashcards_db: TestClient,
    flashcards_db: CharactersRAGDB,
):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckValid"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Qdeck",
        "back": "Adeck",
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200
    uuid = r.json()["uuid"]

    r = client_with_flashcards_db.patch(
        f"/api/v1/flashcards/{uuid}",
        json={"deck_id": 999999},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 400
    det = r.json().get("detail") or {}
    assert det.get("error") == "Deck not found"

    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckDeleted"}, headers=AUTH_HEADERS)
    del_id = r.json()["id"]
    with flashcards_db.transaction() as conn:
        conn.execute("UPDATE decks SET deleted = 1 WHERE id = ?", (del_id,))

    r = client_with_flashcards_db.patch(
        f"/api/v1/flashcards/{uuid}",
        json={"deck_id": del_id},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 400
    det = r.json().get("detail") or {}
    assert det.get("error") == "Deck not found"


def test_bulk_patch_returns_mixed_results(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/decks",
        json={"name": "BulkPatchDeck"},
        headers=AUTH_HEADERS,
    )
    deck_id = r.json()["id"]

    first = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={
            "deck_id": deck_id,
            "front": "Original first",
            "back": "Original back",
        },
        headers=AUTH_HEADERS,
    )
    second = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={
            "deck_id": deck_id,
            "front": "Plain front",
            "back": "Plain back",
        },
        headers=AUTH_HEADERS,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    first_card = first.json()
    second_card = second.json()

    response = client_with_flashcards_db.patch(
        "/api/v1/flashcards/bulk",
        json=[
            {
                "uuid": first_card["uuid"],
                "front": "Updated front",
                "expected_version": first_card["version"],
            },
            {
                "uuid": second_card["uuid"],
                "model_type": "cloze",
                "front": "Not a cloze",
                "expected_version": second_card["version"],
            },
        ],
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["status"] == "updated"
    assert data["results"][0]["flashcard"]["front"] == "Updated front"
    assert data["results"][1]["status"] == "validation_error"
    assert data["results"][1]["error"]["invalid_fields"] == ["front"]


def test_bulk_patch_reports_conflict_without_rolling_back_siblings(
    client_with_flashcards_db: TestClient,
):
    first = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={"front": "Sibling front", "back": "Sibling back"},
        headers=AUTH_HEADERS,
    )
    second = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={"front": "Conflict front", "back": "Conflict back"},
        headers=AUTH_HEADERS,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    first_card = first.json()
    second_card = second.json()

    concurrent = client_with_flashcards_db.patch(
        f"/api/v1/flashcards/{second_card['uuid']}",
        json={
            "front": "Other update",
            "expected_version": second_card["version"],
        },
        headers=AUTH_HEADERS,
    )
    assert concurrent.status_code == 200

    response = client_with_flashcards_db.patch(
        "/api/v1/flashcards/bulk",
        json=[
            {
                "uuid": first_card["uuid"],
                "back": "Saved sibling",
                "expected_version": first_card["version"],
            },
            {
                "uuid": second_card["uuid"],
                "back": "Conflicted edit",
                "expected_version": second_card["version"],
            },
        ],
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["status"] == "updated"
    assert data["results"][0]["flashcard"]["back"] == "Saved sibling"
    assert data["results"][1]["status"] == "conflict"

    current = client_with_flashcards_db.get(
        f"/api/v1/flashcards/id/{first_card['uuid']}",
        headers=AUTH_HEADERS,
    )
    assert current.status_code == 200
    assert current.json()["back"] == "Saved sibling"


def test_bulk_patch_classifies_deleted_deck_and_missing_card(
    client_with_flashcards_db: TestClient,
    flashcards_db: CharactersRAGDB,
):
    live_deck = client_with_flashcards_db.post(
        "/api/v1/flashcards/decks",
        json={"name": "LiveBulkPatchDeck"},
        headers=AUTH_HEADERS,
    )
    deleted_deck = client_with_flashcards_db.post(
        "/api/v1/flashcards/decks",
        json={"name": "DeletedBulkPatchDeck"},
        headers=AUTH_HEADERS,
    )
    assert live_deck.status_code == 200
    assert deleted_deck.status_code == 200
    deleted_deck_id = deleted_deck.json()["id"]
    with flashcards_db.transaction() as conn:
        conn.execute("UPDATE decks SET deleted = 1 WHERE id = ?", (deleted_deck_id,))

    live_card = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={
            "deck_id": live_deck.json()["id"],
            "front": "Live card",
            "back": "Live back",
        },
        headers=AUTH_HEADERS,
    )
    assert live_card.status_code == 200
    card = live_card.json()

    response = client_with_flashcards_db.patch(
        "/api/v1/flashcards/bulk",
        json=[
            {
                "uuid": card["uuid"],
                "deck_id": deleted_deck_id,
                "expected_version": card["version"],
            },
            {
                "uuid": str(uuid.uuid4()),
                "front": "No card",
                "expected_version": 1,
            },
        ],
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["status"] == "validation_error"
    assert data["results"][0]["error"]["invalid_deck_ids"] == [deleted_deck_id]
    assert data["results"][1]["status"] == "not_found"


def test_export_apkg_include_reverse_no_duplication_for_basic_reverse(client_with_flashcards_db: TestClient):
    # Create deck and a basic_reverse card
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckThree"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Alpha",
        "back": "Omega",
        "model_type": "basic_reverse"
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200

    # Export with include_reverse=true; still should be only two cards (ord 0 and 1)
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg", "include_reverse": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    try:
        with zf.open('collection.anki2') as f:
            data = f.read()
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'col.anki2')
            with open(p, 'wb') as fh:
                fh.write(data)
            conn = sqlite3.connect(p)
            try:
                notes = conn.execute("SELECT id FROM notes").fetchall()
                assert len(notes) == 1
                nid = notes[0][0]
                cards = conn.execute("SELECT nid, ord FROM cards").fetchall()
                assert len(cards) == 2
                assert all(c[0] == nid for c in cards)
                assert sorted(c[1] for c in cards) == [0, 1]
            finally:
                conn.close()
    finally:
        zf.close()


def test_export_csv_escapes_specials_and_multiline(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "SpecDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    special_front = "Line1\nLine\t2\nEmoji: 😀"
    special_back = "Tab\tSeparated\nNewline"
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": special_front,
        "back": special_back,
        "notes": "Note\nWith\tTabs",
        "tags": ["spec"]
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200

    r = client_with_flashcards_db.get("/api/v1/flashcards/export", headers=AUTH_HEADERS)
    assert r.status_code == 200
    text = r.content.decode('utf-8')
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 1
    cols = lines[0].split('\t')
    assert len(cols) == 5
    # No embedded tabs/newlines in any column (other than separators)
    for c in cols:
        assert '\n' not in c and '\r' not in c and '\t' not in c


def test_import_tsv_creates_cards_and_decks(client_with_flashcards_db: TestClient):
    # Build TSV content with two lines
    content = (
        "DeckA\tFront A\tBack A\talpha beta\tNote A\n"
        "DeckB\tFront B\tBack B\tgamma\tNote B\n"
    )
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 2
    # List flashcards and verify deck names and tags present in list output
    r = client_with_flashcards_db.get("/api/v1/flashcards", headers=AUTH_HEADERS)
    assert r.status_code == 200
    items = r.json().get('items', [])
    # We expect at least two entries from import
    assert any(it.get('deck_name') == 'DeckA' and 'alpha' in (json.loads(it.get('tags_json') or '[]')) for it in items)
    assert any(it.get('deck_name') == 'DeckB' and 'gamma' in (json.loads(it.get('tags_json') or '[]')) for it in items)


def test_import_tsv_with_header_modeltype_extra(client_with_flashcards_db: TestClient):
    header = "Deck\tFront\tBack\tTags\tNotes\tExtra\tModelType\tReverse\n"
    rows = (
        "DeckC\tF1\tB1\talpha\tN1\tE1\tbasic_reverse\ttrue\n"
        "DeckC\tCloze {{c1::x}}\t\tctag\tCN\tCE\tcloze\tfalse\n"
    )
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    # List back
    r = client_with_flashcards_db.get("/api/v1/flashcards", headers=AUTH_HEADERS)
    items = r.json().get('items', [])
    # Find basic_reverse card
    br = next(it for it in items if it.get('front') == 'F1')
    assert br['model_type'] == 'basic_reverse'
    assert br['reverse'] is True
    assert br.get('extra') == 'E1'
    # Find cloze
    cz = next(it for it in items if it.get('model_type') == 'cloze')
    assert '{{c1::x}}' in cz.get('front')
    assert cz.get('extra') == 'CE'


def test_import_tsv_with_deckdescription_and_iscloze(client_with_flashcards_db: TestClient):
    header = "Deck\tFront\tBack\tTags\tNotes\tDeckDescription\tIsCloze\n"
    rows = (
        "DeckD\tCloze {{c1::zz}}\t\tztag\tZN\tThis is a described deck\ttrue\n"
    )
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    # Verify deck description persisted
    r = client_with_flashcards_db.get("/api/v1/flashcards/decks", headers=AUTH_HEADERS)
    assert r.status_code == 200
    decks = r.json()
    deck = next(d for d in decks if d.get('name') == 'DeckD')
    assert deck.get('description') == 'This is a described deck'
    # Verify imported card is cloze
    r = client_with_flashcards_db.get("/api/v1/flashcards")
    items = r.json().get('items', [])
    card = next(it for it in items if it.get('deck_name') == 'DeckD')
    assert card.get('is_cloze') is True
    assert card.get('model_type') == 'cloze'


def test_export_csv_with_header_and_custom_delimiter(client_with_flashcards_db: TestClient):
    # Create deck/card
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DelimDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "F",
        "back": "B",
        "notes": "N",
        "tags": ["t1", "t2"]
    })
    assert r.status_code == 200
    # Export with delimiter ';' and header
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"delimiter": ";", "include_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.headers.get('content-type', '').startswith('text/csv')
    text = r.content.decode('utf-8')
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) >= 2
    header = lines[0]
    assert header == 'Deck;Front;Back;Tags;Notes'
    cols = lines[1].split(';')
    assert len(cols) == 5
    assert cols[0] == 'DelimDeck'
    # Ensure no tabs present
    assert '\t' not in lines[0] and '\t' not in lines[1]


def test_export_csv_extended_header_and_values(client_with_flashcards_db: TestClient):
    # Create deck/card with extra + reverse
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "ExtDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Fext",
        "back": "Bext",
        "extra": "Xtra",
        "model_type": "basic_reverse"
    })
    assert r.status_code == 200
    # Export with extended header
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"delimiter": ";", "include_header": True, "extended_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    text = r.content.decode('utf-8')
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) >= 2
    header = lines[0]
    assert header == 'Deck;Front;Back;Tags;Notes;Extra;Reverse'
    # Check row contains extra and reverse column values
    cols = lines[1].split(';')
    assert len(cols) == 7
    assert cols[0] == 'ExtDeck'
    assert cols[5] == 'Xtra'
    assert cols[6] in ('true', 'false')


def test_import_minimal_header_front_back_default_deck(client_with_flashcards_db: TestClient):
    header = "Front\tBack\n"
    rows = "Qmin\tAmin\n"
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    # Default deck should exist and card should belong to it
    r = client_with_flashcards_db.get("/api/v1/flashcards/decks", headers=AUTH_HEADERS)
    decks = r.json()
    assert any(d.get('name') == 'Default' for d in decks)
    r = client_with_flashcards_db.get("/api/v1/flashcards")
    items = r.json().get('items', [])
    found = next((it for it in items if it.get('front') == 'Qmin' and it.get('back') == 'Amin'), None)
    assert found is not None
    assert found.get('deck_name') == 'Default'


def test_round_trip_import_export_extra_reverse(client_with_flashcards_db: TestClient):
    # Import TSV with Extra and Reverse
    header = "Deck\tFront\tBack\tTags\tNotes\tExtra\tReverse\n"
    rows = "DeckR\tFr\tBk\ttr\tnt\tXVal\ttrue\n"
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    # Export CSV extended
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"delimiter": ";", "include_header": True, "extended_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    txt = r.content.decode('utf-8')
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    # Find the DeckR row and assert Extra/Reverse values
    row = next(ln for ln in lines[1:] if ln.startswith('DeckR;'))
    cols = row.split(';')
    assert cols[0] == 'DeckR' and cols[1] == 'Fr' and cols[2] == 'Bk'
    assert cols[5] == 'XVal' and cols[6] in ('true', 'false')
    # Export APKG and assert two cards (reverse)
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    import io, sqlite3, zipfile, tempfile, os
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    try:
        with zf.open('collection.anki2') as f:
            data = f.read()
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'col.anki2')
            with open(p, 'wb') as fh:
                fh.write(data)
            conn = sqlite3.connect(p)
            try:
                notes = conn.execute("SELECT id FROM notes").fetchall()
                # At least one note for DeckR
                assert len(notes) >= 1
                # cards: ensure at least one note has two cards
                nids = [n[0] for n in notes]
                has_two = False
                for nid in nids:
                    cnt = conn.execute("SELECT COUNT(*) FROM cards WHERE nid=?", (nid,)).fetchone()[0]
                    if cnt == 2:
                        has_two = True
                        break
                assert has_two
            finally:
                conn.close()
    finally:
        zf.close()


def test_export_apkg_uses_due_at_for_review_cards(client_with_flashcards_db: TestClient, flashcards_db: CharactersRAGDB):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DueDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Due Q",
        "back": "Due A"
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200
    card = r.json()
    card_uuid = card["uuid"]

    # Force a review state with a specific due_at
    due_at = "2030-01-15T00:00:00Z"
    with flashcards_db.transaction() as conn:
        conn.execute(
            "UPDATE flashcards SET repetitions = 3, interval_days = 10, due_at = ? WHERE uuid = ?",
            (due_at, card_uuid),
        )

    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    try:
        with zf.open('collection.anki2') as f:
            data = f.read()
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'col.anki2')
            with open(p, 'wb') as fh:
                fh.write(data)
            conn = sqlite3.connect(p)
            try:
                col = conn.execute("SELECT crt FROM col").fetchone()
                assert col
                crt = int(col[0])
                due_dt = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
                expected_due = max(1, int((due_dt.timestamp() - crt) / 86400.0))
                note_id = conn.execute("SELECT id FROM notes WHERE flds LIKE ?", ("Due Q%",)).fetchone()[0]
                due = conn.execute("SELECT due FROM cards WHERE nid = ?", (note_id,)).fetchone()[0]
                assert due == expected_due
            finally:
                conn.close()
    finally:
        zf.close()


def test_import_malformed_rows_reported(client_with_flashcards_db: TestClient):
    # Missing Front field entirely
    header = "Deck\tBack\tTags\tNotes\n"
    rows = "BadDeck\tOnlyBack\talpha\tSomeNote\n"
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    # Should import 0 and report an error
    assert data.get('imported') == 0
    errs = data.get('errors', [])
    assert len(errs) == 1
    assert 'Missing required field' in errs[0].get('error', '')
    # No cards created
    r = client_with_flashcards_db.get("/api/v1/flashcards")
    assert r.status_code == 200
    assert len(r.json().get('items', [])) == 0


def test_import_malformed_missing_deck_with_header(client_with_flashcards_db: TestClient):
    # Header includes Deck, but row has empty Deck
    header = "Deck\tFront\tBack\tTags\tNotes\n"
    rows = "\tFrontOnly\tB\ta\tn\n"  # first field empty deck
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 0
    errs = data.get('errors', [])
    assert any('Missing required field: Deck' in e.get('error', '') for e in errs)


def test_import_malformed_invalid_cloze(client_with_flashcards_db: TestClient):
    # Header declares cloze model, but front lacks cN pattern
    header = "Deck\tFront\tBack\tTags\tNotes\tModelType\n"
    rows = "CDeck\tNot a cloze\t\t\t\tcloze\n"
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 0
    errs = data.get('errors', [])
    assert any('Invalid cloze' in e.get('error', '') for e in errs)


def test_import_oversize_field_rejected(client_with_flashcards_db: TestClient):
    # Front exceeds MAX_FIELD_LENGTH (8192)
    long_front = 'F' * 9000
    header = "Deck\tFront\tBack\tTags\tNotes\n"
    rows = f"LD\t{long_front}\tB\tT\tN\n"
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 0
    errs = data.get('errors', [])
    assert any('Field too long' in e.get('error', '') for e in errs)


def test_import_oversize_line_rejected(client_with_flashcards_db: TestClient):
    # Construct a very long single line (> 32768)
    big = 'A' * 33000
    header = "Deck\tFront\tBack\tTags\tNotes\n"
    rows = f"LD\t{big}\tB\tT\tN\n"
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 0
    errs = data.get('errors', [])
    assert any('Line too long' in e.get('error', '') for e in errs)


def test_import_respects_max_lines_cap(client_with_flashcards_db: TestClient, monkeypatch):
    # Limit to 3 lines via env override
    monkeypatch.setenv('FLASHCARDS_IMPORT_MAX_LINES', '3')
    header = "Deck\tFront\tBack\tTags\tNotes\n"
    rows = "".join([f"D\tF{i}\tB\tT\tN\n" for i in range(1, 6)])  # 5 rows
    content = header + rows
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True})
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 3
    errs = data.get('errors', [])
    # Should include a cap message
    assert any('Maximum import line limit' in (e.get('error') or '') for e in errs)


def test_import_respects_query_param_caps(client_with_flashcards_db: TestClient, monkeypatch):
    # Env cap high, query lowers to 2
    monkeypatch.setenv('FLASHCARDS_IMPORT_MAX_LINES', '10')
    header = "Deck\tFront\tBack\tTags\tNotes\n"
    rows = "".join([f"D\tF{i}\tB\tT\tN\n" for i in range(1, 5)])  # 4 rows
    content = header + rows
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards/import",
        params={"max_lines": 2},
        json={"content": content, "has_header": True},
        headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 2
    errs = data.get('errors', [])
    assert any('Maximum import line limit' in (e.get('error') or '') for e in errs)


def test_config_endpoint_flashcards_import_limits(client_with_flashcards_db: TestClient, monkeypatch):
    monkeypatch.setenv('FLASHCARDS_IMPORT_MAX_LINES', '999')
    monkeypatch.setenv('FLASHCARDS_IMPORT_MAX_LINE_LENGTH', '12345')
    monkeypatch.setenv('FLASHCARDS_IMPORT_MAX_FIELD_LENGTH', '2345')
    r = client_with_flashcards_db.get("/api/v1/config/flashcards-import-limits", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get('max_lines') == 999
    assert data.get('max_line_length') == 12345
    assert data.get('max_field_length') == 2345
    assert 'query_params' in data.get('overrides', {})


def test_structured_preview_endpoint_returns_drafts(client_with_flashcards_db: TestClient):
    payload = {
        "content": "Q: What is ATP?\nA: Primary energy currency.\n"
    }

    response = client_with_flashcards_db.post(
        "/api/v1/flashcards/import/structured/preview",
        json=payload,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["detected_format"] == "qa_labels"
    assert data["drafts"][0]["front"] == "What is ATP?"
    assert data["drafts"][0]["back"] == "Primary energy currency."
    assert data["errors"] == []


def test_structured_preview_respects_line_caps(
    client_with_flashcards_db: TestClient,
    monkeypatch,
):
    monkeypatch.setenv("FLASHCARDS_IMPORT_MAX_LINES", "2")

    payload = {
        "content": "Q: One\nA: First\nQ: Two\nA: Second\n"
    }

    response = client_with_flashcards_db.post(
        "/api/v1/flashcards/import/structured/preview",
        json=payload,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["drafts"]) == 1
    assert any(
        "Maximum preview line limit" in error["error"]
        for error in data["errors"]
    )


def test_import_json_file_basic(client_with_flashcards_db: TestClient):
    import json as _json
    payload = [
        {"deck": "JDeck", "front": "JF1", "back": "JB1", "tags": ["jt1", "jt2"], "extra": "JE1", "reverse": True},
        {"deck": "JDeck", "front": "Cloze {{c1::xx}}", "model_type": "cloze", "extra": "JCE"}
    ]
    files = {
        'file': ('cards.json', _json.dumps(payload), 'application/json')
    }
    r = client_with_flashcards_db.post("/api/v1/flashcards/import/json", files=files, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 2
    # Verify created
    r = client_with_flashcards_db.get("/api/v1/flashcards", headers=AUTH_HEADERS)
    items = r.json().get('items', [])
    assert any(it.get('deck_name') == 'JDeck' and it.get('front') == 'JF1' for it in items)
    assert any(it.get('model_type') == 'cloze' and '{{c1::' in it.get('front') for it in items)


def test_import_json_caps_and_errors(client_with_flashcards_db: TestClient, monkeypatch):
    import json as _json
    # Set env caps low
    monkeypatch.setenv('FLASHCARDS_IMPORT_MAX_LINES', '1')
    payload = [
        {"deck": "J1", "front": "F1", "back": "B1"},
        {"deck": "J2", "front": "F2", "back": "B2"}
    ]
    files = {'file': ('cards.json', _json.dumps(payload), 'application/json')}
    r = client_with_flashcards_db.post("/api/v1/flashcards/import/json", files=files, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 1
    errs = data.get('errors', [])
    assert any('Maximum import item limit' in (e.get('error') or '') for e in errs)
    # Invalid cloze error
    payload2 = [{"front": "not cloze", "model_type": "cloze"}]
    files2 = {'file': ('cards.json', _json.dumps(payload2), 'application/json')}
    r2 = client_with_flashcards_db.post("/api/v1/flashcards/import/json", files=files2, headers=AUTH_HEADERS)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2.get('imported') == 0
    errs2 = data2.get('errors', [])
    assert any('Invalid cloze' in (e.get('error') or '') for e in errs2)


def test_import_json_unicode_preserved(client_with_flashcards_db: TestClient):
    import json as _json
    payload = [
        {"deck": "JUnicode", "front": "Hello 😀", "back": "World"}
    ]
    files = {'file': ('cards.json', _json.dumps(payload), 'application/json')}
    r = client_with_flashcards_db.post("/api/v1/flashcards/import/json", files=files, headers=AUTH_HEADERS)
    assert r.status_code == 200
    r2 = client_with_flashcards_db.get("/api/v1/flashcards", headers=AUTH_HEADERS)
    assert r2.status_code == 200
    items = r2.json().get('items', [])
    assert any('😀' in (it.get('front') or '') for it in items)


def test_import_apkg_file_basic(client_with_flashcards_db: TestClient):
    payload_rows = [
        {
            "deck_name": "APKG Deck",
            "model_type": "basic",
            "front": "APKG Q1",
            "back": "APKG A1",
            "extra": "extra 1",
            "tags_json": json.dumps(["apkg", "basic"]),
        },
        {
            "deck_name": "APKG Deck",
            "model_type": "basic_reverse",
            "front": "APKG Q2",
            "back": "APKG A2",
            "extra": "extra 2",
            "tags_json": json.dumps(["apkg", "reverse"]),
            "reverse": True,
        },
        {
            "deck_name": "APKG Deck",
            "model_type": "cloze",
            "front": "APKG {{c1::cloze}}",
            "back": "",
            "extra": "cloze extra",
            "tags_json": json.dumps(["apkg", "cloze"]),
        },
    ]
    apkg = export_apkg_from_rows(payload_rows)
    files = {
        "file": ("flashcards.apkg", apkg, "application/apkg"),
    }
    r = client_with_flashcards_db.post("/api/v1/flashcards/import/apkg", files=files, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get("imported") == 3
    assert data.get("errors") == []

    r2 = client_with_flashcards_db.get("/api/v1/flashcards", headers=AUTH_HEADERS)
    assert r2.status_code == 200
    items = r2.json().get("items", [])
    by_front = {item.get("front"): item for item in items}
    assert "APKG Q1" in by_front
    assert "APKG Q2" in by_front
    assert "APKG {{c1::cloze}}" in by_front
    assert by_front["APKG Q2"].get("model_type") == "basic_reverse"
    assert by_front["APKG Q2"].get("reverse") is True
    assert by_front["APKG {{c1::cloze}}"].get("model_type") == "cloze"
    assert by_front["APKG {{c1::cloze}}"].get("is_cloze") is True


def test_import_apkg_preserves_scheduling_fields(client_with_flashcards_db: TestClient):
    payload_rows = [
        {
            "deck_name": "SchedDeck",
            "model_type": "basic",
            "front": "New Card",
            "back": "A0",
            "ef": 2.5,
            "interval_days": 0,
            "repetitions": 0,
            "lapses": 0,
            "due_at": None,
        },
        {
            "deck_name": "SchedDeck",
            "model_type": "basic",
            "front": "Review Card",
            "back": "A1",
            "ef": 2.1,
            "interval_days": 14,
            "repetitions": 5,
            "lapses": 2,
            "due_at": None,
        },
    ]
    apkg = export_apkg_from_rows(payload_rows)
    files = {
        "file": ("sched.apkg", apkg, "application/apkg"),
    }
    r = client_with_flashcards_db.post("/api/v1/flashcards/import/apkg", files=files, headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json().get("imported") == 2

    r2 = client_with_flashcards_db.get("/api/v1/flashcards", headers=AUTH_HEADERS)
    assert r2.status_code == 200
    by_front = {item.get("front"): item for item in r2.json().get("items", [])}
    assert by_front["New Card"].get("repetitions") == 0
    assert by_front["New Card"].get("interval_days") == 0
    assert by_front["New Card"].get("due_at") is None

    review = by_front["Review Card"]
    assert review.get("repetitions") == 5
    assert review.get("interval_days") == 14
    assert review.get("lapses") == 2
    assert pytest.approx(review.get("ef"), rel=1e-3) == 2.1
    assert review.get("due_at") is not None


def test_import_apkg_invalid_archive_returns_400(client_with_flashcards_db: TestClient):
    files = {
        "file": ("bad.apkg", b"not a zip archive", "application/apkg"),
    }
    r = client_with_flashcards_db.post("/api/v1/flashcards/import/apkg", files=files, headers=AUTH_HEADERS)
    assert r.status_code == 400
    assert "Invalid APKG archive" in r.json().get("detail", "")


def test_export_csv_preserves_quotes_and_no_extra_separators(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "QuoteDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "\"Quoted\" Front",
        "back": "Back with \"quotes\"",
        "notes": "Note with 'single' and \"double\" quotes",
        "tags": ["qtag"]
    })
    assert r.status_code == 200

    r = client_with_flashcards_db.get("/api/v1/flashcards/export", headers=AUTH_HEADERS)
    assert r.status_code == 200
    text = r.content.decode('utf-8')
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 1
    cols = lines[0].split('\t')
    assert len(cols) == 5
    # Quotes should be preserved; no extra separators injected
    assert '"Quoted" Front' in cols[1]
    assert 'Back with "quotes"' in cols[2]
    assert 'Note with' in cols[4]
    # No stray tabs/newlines
    for c in cols:
        assert '\n' not in c and '\r' not in c and '\t' not in c


def test_bulk_create_modeltype_reverse_and_tag_linkage(client_with_flashcards_db: TestClient):
    # Create a deck first
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "BulkDeck"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    deck_id = r.json()["id"]

    payload = [
        {
            "deck_id": deck_id,
            "front": "F1",
            "back": "B1",
            "extra": "E1",
            "model_type": "basic_reverse",
            "tags": ["t1", "t2"],
        },
        {
            "deck_id": deck_id,
            "front": "Cloze {{c1::x}}",
            "back": "",
            "is_cloze": True,
            "tags": ["cz"],
        },
    ]
    r = client_with_flashcards_db.post("/api/v1/flashcards/bulk", json=payload, headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data.get("count") == 2
    items = data.get("items", [])
    assert len(items) == 2
    first = next(i for i in items if i.get("front") == "F1")
    assert first.get("model_type") == "basic_reverse" and first.get("reverse") is True
    assert first.get("extra") == "E1"
    uuid1 = first.get("uuid")
    # Verify keyword linkage for first item
    r = client_with_flashcards_db.get(f"/api/v1/flashcards/{uuid1}/tags", headers=AUTH_HEADERS)
    assert r.status_code == 200
    kw_texts = {kw.get("keyword") for kw in r.json().get("items", [])}
    assert {"t1", "t2"}.issubset(kw_texts)

    second = next(i for i in items if i.get("front", "").startswith("Cloze "))
    assert second.get("model_type") == "cloze"
    assert second.get("is_cloze") is True


def test_create_single_links_tags_to_keywords(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "SingleDeck"}, headers=AUTH_HEADERS)
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Tagged Single",
        "back": "Ans",
        "tags": ["sx", "sy"],
    }, headers=AUTH_HEADERS)
    assert r.status_code == 200
    card = r.json()
    uuid = card.get("uuid")
    # Verify linkage
    r = client_with_flashcards_db.get(f"/api/v1/flashcards/{uuid}/tags", headers=AUTH_HEADERS)
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert {"sx", "sy"}.issubset({kw.get("keyword") for kw in items})


def test_create_with_invalid_deck_returns_400(client_with_flashcards_db: TestClient):
    # Use a non-existent deck id
    r = client_with_flashcards_db.post(
        "/api/v1/flashcards",
        json={
            "deck_id": 999999,
            "front": "Q",
            "back": "A"
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 400
    det = r.json().get("detail") or {}
    assert det.get("error") == "Deck not found"
    assert 999999 in (det.get("invalid_deck_ids") or [])


def test_bulk_create_with_invalid_deck_returns_400(client_with_flashcards_db: TestClient):
    # Create a valid deck to mix
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "ValidBulk"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    valid_deck_id = r.json()["id"]
    payload = [
        {"deck_id": valid_deck_id, "front": "Fok", "back": "Bok"},
        {"deck_id": 42424242, "front": "Fbad", "back": "Bbad"},
    ]
    r = client_with_flashcards_db.post("/api/v1/flashcards/bulk", json=payload, headers=AUTH_HEADERS)
    assert r.status_code == 400
    data = r.json()
    # FastAPI wraps detail dict under top-level 'detail'
    det = data.get("detail") or {}
    assert det.get("error")
    assert 42424242 in det.get("invalid_deck_ids", [])
