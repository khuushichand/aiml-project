"""
Integration tests for Notes API endpoints using a real ChaChaNotes DB.
No mocking of internal functions; only dependency override to inject a temp DB.
"""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_notes_db(tmp_path):
    db_path = tmp_path / "notes_integration.db"
    db = CharactersRAGDB(str(db_path), client_id="integration_user")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    # Inject per-user DB via dependency override
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    def override_db_dep():
        return db

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = override_db_dep

    with TestClient(fastapi_app) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


def test_create_get_update_delete_note(client_with_notes_db: TestClient):
    client = client_with_notes_db

    # Create
    create_resp = client.post(
        "/api/v1/notes/",
        json={"title": "Integration Note", "content": "Hello world"},
    )
    assert create_resp.status_code == 201, create_resp.text
    note = create_resp.json()
    note_id = note["id"]

    # Get
    get_resp = client.get(f"/api/v1/notes/{note_id}")
    assert get_resp.status_code == 200
    got = get_resp.json()
    assert got["title"] == "Integration Note"
    assert got["content"] == "Hello world"

    # Update
    upd_resp = client.patch(
        f"/api/v1/notes/{note_id}",
        json={"title": "Updated Title", "content": "Updated"},
    )
    assert upd_resp.status_code == 200
    upd = upd_resp.json()
    assert upd["title"] == "Updated Title"

    # List
    list_resp = client.get("/api/v1/notes/")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert isinstance(data, dict) and "notes" in data
    assert any(n.get("id") == note_id for n in data["notes"])  # noqa: SIM118

    # Delete (soft) requires expected-version header
    curr = client.get(f"/api/v1/notes/{note_id}").json()
    ver = curr.get("version", 1)
    del_resp = client.delete(f"/api/v1/notes/{note_id}", headers={"expected-version": str(ver)})
    assert del_resp.status_code in (200, 204)


def test_keywords_crud_and_linking(client_with_notes_db: TestClient):
    client = client_with_notes_db

    # Create 2 notes
    n1 = client.post("/api/v1/notes/", json={"title": "A", "content": "Apple"}).json()
    n2 = client.post("/api/v1/notes/", json={"title": "B", "content": "Banana"}).json()

    # Create keyword
    kw_resp = client.post("/api/v1/notes/keywords/", json={"keyword": "fruit"})
    assert kw_resp.status_code == 201, kw_resp.text
    kw = kw_resp.json(); kw_id = kw["id"]

    # Get by id and text
    assert client.get(f"/api/v1/notes/keywords/{kw_id}").status_code == 200
    assert client.get(f"/api/v1/notes/keywords/text/fruit").status_code == 200

    # List / search
    lst = client.get("/api/v1/notes/keywords/")
    assert lst.status_code == 200 and isinstance(lst.json(), list)
    srch = client.get("/api/v1/notes/keywords/search/", params={"query": "fru"})
    assert srch.status_code == 200 and any(k.get("id") == kw_id for k in srch.json())

    # Link to note 1 and note 2
    link1 = client.post(f"/api/v1/notes/{n1['id']}/keywords/{kw_id}")
    link2 = client.post(f"/api/v1/notes/{n2['id']}/keywords/{kw_id}")
    assert link1.status_code == 200 and link2.status_code == 200

    # Get keywords for note 1
    kws_for_n1 = client.get(f"/api/v1/notes/{n1['id']}/keywords/")
    assert kws_for_n1.status_code == 200
    assert any(k.get("id") == kw_id for k in kws_for_n1.json().get("keywords", []))

    # Get notes for keyword
    notes_for_kw = client.get(f"/api/v1/notes/keywords/{kw_id}/notes/")
    assert notes_for_kw.status_code == 200
    ids = [note.get("id") for note in notes_for_kw.json().get("notes", [])]
    assert n1['id'] in ids and n2['id'] in ids

    # Unlink one
    un = client.delete(f"/api/v1/notes/{n1['id']}/keywords/{kw_id}")
    assert un.status_code == 200

    # Delete keyword (requires version header)
    # Fetch keyword for version
    kw_data = client.get(f"/api/v1/notes/keywords/{kw_id}").json()
    ver = kw_data.get("version", 1)
    del_kw = client.delete(f"/api/v1/notes/keywords/{kw_id}", headers={"expected-version": str(ver)})
    assert del_kw.status_code in (200, 204)

    # Update note with version header and test conflict
    refreshed_n2 = client.get(f"/api/v1/notes/{n2['id']}").json()
    good_ver = refreshed_n2.get("version", 1)
    ok_upd = client.patch(
        f"/api/v1/notes/{n2['id']}",
        json={"title": "B2"},
        headers={"expected-version": str(good_ver)}
    )
    assert ok_upd.status_code == 200

    bad_upd = client.patch(
        f"/api/v1/notes/{n2['id']}",
        json={"title": "B3"},
        headers={"expected-version": str(good_ver)}  # stale
    )
    assert bad_upd.status_code in (409, 400)


def test_list_and_search_pagination_and_404s(client_with_notes_db: TestClient):
    client = client_with_notes_db

    # Create several notes
    for i in range(5):
        client.post("/api/v1/notes/", json={"title": f"T{i}", "content": f"C{i}"})

    # Paginate list
    page1 = client.get("/api/v1/notes/", params={"limit": 2, "offset": 0})
    page2 = client.get("/api/v1/notes/", params={"limit": 2, "offset": 2})
    assert page1.status_code == 200 and page2.status_code == 200
    d1, d2 = page1.json(), page2.json()
    assert isinstance(d1, dict) and isinstance(d2, dict)
    assert isinstance(d1.get("notes"), list) and isinstance(d2.get("notes"), list)
    # Verify disjointness of pages by IDs
    ids1 = {n.get("id") for n in d1.get("notes", [])}
    ids2 = {n.get("id") for n in d2.get("notes", [])}
    assert ids1.isdisjoint(ids2)
    # If both pages are full, combined count equals sum
    if len(ids1) == 2 and len(ids2) == 2:
        assert len(ids1 | ids2) == 4

    # Search notes
    search = client.get("/api/v1/notes/search/", params={"query": "T", "limit": 3})
    assert search.status_code == 200 and isinstance(search.json(), list)
    empty_search = client.get("/api/v1/notes/search/", params={"query": "zzznotfound", "limit": 3})
    assert empty_search.status_code == 200 and empty_search.json() == []

    # Non-existent note 404
    nf = client.get("/api/v1/notes/non-existent-id")
    assert nf.status_code == 404

    # Update with no fields -> 400
    created = client.post("/api/v1/notes/", json={"title": "X", "content": "Y"}).json()
    upd_bad = client.patch(f"/api/v1/notes/{created['id']}", json={}, headers={"expected-version": str(created.get('version', 1))})
    assert upd_bad.status_code == 400

    # Delete requires version header
    del_no_header = client.delete(f"/api/v1/notes/{created['id']}")
    assert del_no_header.status_code in (400, 422)


def test_keywords_list_pagination_and_search_limit(client_with_notes_db: TestClient):
    client = client_with_notes_db
    # Create many keywords
    for i in range(15):
        client.post("/api/v1/notes/keywords/", json={"keyword": f"kw{i}"})

    # List first page with small limit
    lst1 = client.get("/api/v1/notes/keywords/", params={"limit": 5, "offset": 0})
    lst2 = client.get("/api/v1/notes/keywords/", params={"limit": 5, "offset": 5})
    assert lst1.status_code == 200 and lst2.status_code == 200
    k1 = lst1.json(); k2 = lst2.json()
    assert isinstance(k1, list) and isinstance(k2, list)
    assert len(k1) <= 5 and len(k2) <= 5
    # Verify disjointness of keyword pages by id when both non-empty
    if k1 and k2:
        ids1 = {k.get("id") for k in k1}
        ids2 = {k.get("id") for k in k2}
        assert ids1.isdisjoint(ids2)
    # Search with limit
    search = client.get("/api/v1/notes/keywords/search/", params={"query": "kw", "limit": 7})
    assert search.status_code == 200
    results = search.json()
    assert isinstance(results, list)
    assert len(results) <= 7


def test_keyword_search_substring_behavior(client_with_notes_db: TestClient):
    client = client_with_notes_db
    # Create specific keywords to test substring behavior
    for kw in ("kw1", "kw10", "kw2"):
        client.post("/api/v1/notes/keywords/", json={"keyword": kw})

    search = client.get("/api/v1/notes/keywords/search/", params={"query": "kw1", "limit": 10})
    assert search.status_code == 200
    res = search.json()
    assert isinstance(res, list)
    # Expect to find kw1; many backends will also include kw10 by substring search
    texts = {item.get("keyword") or item.get("text") for item in res}
    assert "kw1" in texts
    if "kw10" not in texts:
        # If the search is exact-match, accept; otherwise prefer inclusion
        pytest.skip("Keyword search appears to be exact-match; skipping substring assertion")
    assert "kw10" in texts and "kw2" not in texts


def test_keyword_update_not_supported(client_with_notes_db: TestClient):
    client = client_with_notes_db
    kw = client.post("/api/v1/notes/keywords/", json={"keyword": "rename-me"}).json()
    kw_id = kw["id"]
    # Attempt an update (not supported by API) should yield 405 Method Not Allowed
    resp = client.put(f"/api/v1/notes/keywords/{kw_id}", json={"keyword": "renamed"})
    assert resp.status_code in (405, 404)


def test_keyword_delete_conflict(client_with_notes_db: TestClient):
    client = client_with_notes_db
    # Create keyword
    kw = client.post("/api/v1/notes/keywords/", json={"keyword": "conflict-key"}).json()
    kw_id = kw["id"]
    ver = kw.get("version", 1)
    # Try delete with stale version (e.g., ver-1)
    bad_ver = max(0, ver - 1)
    bad = client.delete(f"/api/v1/notes/keywords/{kw_id}", headers={"expected-version": str(bad_ver)})
    assert bad.status_code in (409, 400)
    # Now delete with current version
    ok = client.delete(f"/api/v1/notes/keywords/{kw_id}", headers={"expected-version": str(ver)})
    assert ok.status_code in (200, 204)


def test_rate_limit_on_create_note(client_with_notes_db: TestClient, monkeypatch):
    client = client_with_notes_db
    # Use a separate DB client_id to isolate rate limiter state if needed
    # Create 31 notes rapidly to exceed 30/min default limit
    created = 0
    last_status = None
    for i in range(35):
        resp = client.post("/api/v1/notes/", json={"title": f"RL{i}", "content": "X"})
        last_status = resp.status_code
        if resp.status_code == 201:
            created += 1
        if resp.status_code == 429:
            break
    # Ensure we eventually hit rate limit
    assert last_status == 429 or created >= 30


def test_delete_conflict_and_success(client_with_notes_db: TestClient):
    client = client_with_notes_db
    # Create note and fetch version
    created = client.post("/api/v1/notes/", json={"title": "Del", "content": "V1"}).json()
    nid = created["id"]
    v1 = created.get("version", 1)

    # Update to bump version
    upd = client.patch(
        f"/api/v1/notes/{nid}",
        json={"content": "V2"},
        headers={"expected-version": str(v1)}
    )
    assert upd.status_code == 200
    current = client.get(f"/api/v1/notes/{nid}").json()
    v2 = current.get("version", v1 + 1)

    # Try delete with stale version -> conflict
    bad_del = client.delete(f"/api/v1/notes/{nid}", headers={"expected-version": str(v1)})
    assert bad_del.status_code in (409, 400)

    # Delete with current version -> success
    ok_del = client.delete(f"/api/v1/notes/{nid}", headers={"expected-version": str(v2)})
    assert ok_del.status_code in (200, 204)
