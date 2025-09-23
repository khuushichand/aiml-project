import json
import uuid
import io
import zipfile
import sqlite3
import pytest
from fastapi.testclient import TestClient
from loguru import logger

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.tests.test_config import TestConfig


@pytest.fixture(scope="function")
def flashcards_db(tmp_path):
    db_path = tmp_path / "flashcards.db"
    db = CharactersRAGDB(str(db_path), client_id=f"test-{uuid.uuid4().hex[:6]}")
    yield db
    db.close_connection()


@pytest.fixture
def client_with_flashcards_db(flashcards_db: CharactersRAGDB):
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
    def override_get_db():
        logger.info("[TEST] override get_chacha_db_for_user -> flashcards_db")
        try:
            yield flashcards_db
        finally:
            pass
    app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    with TestClient(app) as c:
        c.headers["X-API-KEY"] = TestConfig.TEST_API_KEY
        yield c
    app.dependency_overrides.clear()


def test_export_apkg_basic_integration(client_with_flashcards_db: TestClient):
    # Create deck
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckOne", "description": "d1"})
    assert r.status_code == 200
    deck = r.json()
    deck_id = deck["id"]

    # Create basic card
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "What is 2+2?",
        "back": "4",
        "tags": ["math"]
    })
    assert r.status_code == 200

    # Create reverse card
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "USA capital?",
        "back": "Washington, D.C.",
        "model_type": "basic_reverse"
    })
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
    })
    assert r.status_code == 200

    # Export APKG
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg"})
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
                # Cards: basic=1, reverse adds 1, cloze with c1,c2 adds 2 => total 4
                assert cards == 4
            finally:
                conn.close()
    finally:
        zf.close()


def test_export_apkg_include_reverse_flag_generates_reverse(client_with_flashcards_db: TestClient):
    # Create deck and a plain basic card (no reverse/model_type)
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckTwo"})
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Capital of Japan?",
        "back": "Tokyo"
    })
    card = r.json()
    assert card["model_type"] == "basic"
    assert card["reverse"] is False

    # Export with include_reverse=true
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg", "include_reverse": True})
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


def test_export_csv_shape_and_content(client_with_flashcards_db: TestClient):
    # Create deck and two cards with tags and notes
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "CSVDeck"})
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Q1",
        "back": "A1",
        "notes": "N1",
        "tags": ["alpha", "beta"]
    })
    assert r.status_code == 200
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Q2",
        "back": "A2",
        "notes": "N2",
        "tags": ["gamma"]
    })
    assert r.status_code == 200

    # Export CSV (TSV)
    r = client_with_flashcards_db.get("/api/v1/flashcards/export")
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
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "TagDeck"})
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Tagged Q",
        "back": "Tagged A"
    })
    card = r.json()
    uuid = card["uuid"]

    # Set tags via endpoint
    r = client_with_flashcards_db.put(f"/api/v1/flashcards/{uuid}/tags", json={"tags": ["alpha", "beta"]})
    assert r.status_code == 200
    updated = r.json()
    # tags_json returns JSON string
    tags_json = updated.get("tags_json")
    assert tags_json
    tags = json.loads(tags_json)
    assert set(tags) == {"alpha", "beta"}

    # Verify keyword linkage
    r = client_with_flashcards_db.get(f"/api/v1/flashcards/{uuid}/tags")
    assert r.status_code == 200
    data = r.json()
    items = data.get("items", [])
    kw_texts = {kw.get("keyword") for kw in items}
    assert {"alpha", "beta"}.issubset(kw_texts)


def test_export_apkg_include_reverse_no_duplication_for_basic_reverse(client_with_flashcards_db: TestClient):
    # Create deck and a basic_reverse card
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "DeckThree"})
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "Alpha",
        "back": "Omega",
        "model_type": "basic_reverse"
    })
    assert r.status_code == 200

    # Export with include_reverse=true; still should be only two cards (ord 0 and 1)
    r = client_with_flashcards_db.get("/api/v1/flashcards/export", params={"format": "apkg", "include_reverse": True})
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
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "SpecDeck"})
    deck_id = r.json()["id"]
    special_front = "Line1\nLine\t2\nEmoji: 😀"
    special_back = "Tab\tSeparated\nNewline"
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": special_front,
        "back": special_back,
        "notes": "Note\nWith\tTabs",
        "tags": ["spec"]
    })
    assert r.status_code == 200

    r = client_with_flashcards_db.get("/api/v1/flashcards/export")
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
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content})
    assert r.status_code == 200
    data = r.json()
    assert data.get('imported') == 2
    # List flashcards and verify deck names and tags present in list output
    r = client_with_flashcards_db.get("/api/v1/flashcards")
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
    r = client_with_flashcards_db.post("/api/v1/flashcards/import", json={"content": content, "has_header": True})
    assert r.status_code == 200
    # List back
    r = client_with_flashcards_db.get("/api/v1/flashcards")
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
    # Unicode preserved
    assert '😀' in cols[1]


def test_export_csv_preserves_quotes_and_no_extra_separators(client_with_flashcards_db: TestClient):
    r = client_with_flashcards_db.post("/api/v1/flashcards/decks", json={"name": "QuoteDeck"})
    deck_id = r.json()["id"]
    r = client_with_flashcards_db.post("/api/v1/flashcards", json={
        "deck_id": deck_id,
        "front": "\"Quoted\" Front",
        "back": "Back with \"quotes\"",
        "notes": "Note with 'single' and \"double\" quotes",
        "tags": ["qtag"]
    })
    assert r.status_code == 200

    r = client_with_flashcards_db.get("/api/v1/flashcards/export")
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
