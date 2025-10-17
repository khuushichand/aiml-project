import json
import uuid
import io
import zipfile
import sqlite3
import pytest
from fastapi.testclient import TestClient
from loguru import logger

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
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
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
    def override_get_db():
        logger.info("[TEST] override get_chacha_db_for_user -> flashcards_db")
        try:
            yield flashcards_db
        finally:
            pass
    # Also bypass AuthNZ in tests by returning a fixed user
    async def override_user():
        return User(id=1, username="testuser", email="test@example.com", is_active=True)

    # Apply dependency overrides
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    fastapi_app.dependency_overrides[get_request_user] = override_user

    # Provide a TestClient with default X-API-KEY header for all requests
    default_headers = {"X-API-KEY": TestConfig.TEST_API_KEY}
    with TestClient(fastapi_app, headers=default_headers) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


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
                # Cards: basic=1, reverse adds 1, cloze with c1,c2 adds 2 => total 4
                assert cards == 4
            finally:
                conn.close()
    finally:
        zf.close()


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
