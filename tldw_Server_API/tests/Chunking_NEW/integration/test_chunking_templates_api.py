"""
Integration tests for Chunking Templates API using a real MediaDatabase.
No internal mocks; overrides DI to return a temp per-user DB.
"""

import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_media_db(tmp_path):
    db_path = tmp_path / "media.db"
    db = MediaDatabase(str(db_path), client_id="chunking_user")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    def override_media_db():
        return db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_media_db_for_user] = override_media_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_cannot_modify_or_delete_builtin_template(client_with_media_db: TestClient):
    """Seed a built-in template directly in DB and assert API blocks updates/deletes."""
    client = client_with_media_db

    # Access the underlying DB from the override for setup
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    db = app.dependency_overrides[get_media_db_for_user]()

    # Create a built-in template directly via DB
    builtin_name = "builtin_integration_template"
    tmpl_json = json.dumps({"chunking": {"method": "words", "size": 20}})
    try:
        db.create_chunking_template(
            name=builtin_name,
            template_json=tmpl_json,
            description="Built-in for tests",
            is_builtin=True,
            tags=["builtin"],
            user_id="system"
        )
    except Exception:
        # If already exists, continue
        pass

    # Attempt to update built-in template via API -> expect 400
    upd = client.put(f"/api/v1/chunking/templates/{builtin_name}", json={"description": "should fail"})
    assert upd.status_code == 400

    # Attempt to delete built-in template via API -> expect 400
    dele = client.delete(f"/api/v1/chunking/templates/{builtin_name}")
    assert dele.status_code == 400


def test_templates_crud_and_apply(client_with_media_db: TestClient):
    client = client_with_media_db

    # Validate a minimal template
    valid_payload = {"chunking": {"method": "words", "size": 10, "overlap": 0}}
    vresp = client.post("/api/v1/chunking/templates/validate", json=valid_payload)
    assert vresp.status_code == 200
    assert vresp.json().get("valid") is True

    # Create template
    tmpl_name = "integration_template"
    create_payload = {
        "name": tmpl_name,
        "description": "Integration template",
        "template": valid_payload,
        "tags": ["test"],
        "user_id": "chunking_user"
    }
    c = client.post("/api/v1/chunking/templates", json=create_payload)
    assert c.status_code == 201, c.text

    # List templates and fetch by name
    lst = client.get("/api/v1/chunking/templates")
    assert lst.status_code == 200
    names = [t.get("name") for t in lst.json().get("templates", [])]
    assert tmpl_name in names
    g = client.get(f"/api/v1/chunking/templates/{tmpl_name}")
    assert g.status_code == 200

    # Apply template
    apply_req = {"template_name": tmpl_name, "text": "One two three four five six."}
    a = client.post("/api/v1/chunking/templates/apply", json=apply_req)
    assert a.status_code == 200
    chunks = a.json().get("chunks", [])
    assert isinstance(chunks, list) and len(chunks) >= 1

    # Update template description
    upd = client.put(f"/api/v1/chunking/templates/{tmpl_name}", json={"description": "Updated desc"})
    assert upd.status_code == 200
    assert upd.json().get("description") == "Updated desc"

    # Delete template
    d = client.delete(f"/api/v1/chunking/templates/{tmpl_name}")
    assert d.status_code in (200, 204)


def test_validate_invalid_template(client_with_media_db: TestClient):
    client = client_with_media_db
    bad_payload = {"preprocessing": "should-be-list"}
    r = client.post("/api/v1/chunking/templates/validate", json=bad_payload)
    assert r.status_code == 200
    body = r.json()
    # Should not be valid and should include errors
    assert body.get("valid") is False
    assert body.get("errors")


def test_list_templates_with_filters(client_with_media_db: TestClient):
    client = client_with_media_db
    # Create a custom template with a tag
    tmpl_name = "tagged_template"
    create_payload = {
        "name": tmpl_name,
        "description": "Tagged template",
        "template": {"chunking": {"method": "words", "size": 5}},
        "tags": ["alpha", "beta"],
        "user_id": "chunking_user"
    }
    c = client.post("/api/v1/chunking/templates", json=create_payload)
    assert c.status_code == 201

    # Now list with tags filter
    lst = client.get("/api/v1/chunking/templates", params={"include_builtin": True, "include_custom": True, "tags": ["beta"]})
    assert lst.status_code == 200
    items = lst.json().get("templates", [])
    assert any(t.get("name") == tmpl_name for t in items)


def test_apply_with_override_options(client_with_media_db: TestClient):
    client = client_with_media_db
    tmpl_name = "override_template"
    # Create a simple words-based template
    create_payload = {
        "name": tmpl_name,
        "description": "Template for override test",
        "template": {"chunking": {"method": "words"}},
        "tags": ["override"],
        "user_id": "chunking_user"
    }
    c = client.post("/api/v1/chunking/templates", json=create_payload)
    assert c.status_code == 201, c.text

    text = "one two three four five six seven eight nine ten eleven twelve"
    # Apply default
    a1 = client.post("/api/v1/chunking/templates/apply", json={"template_name": tmpl_name, "text": text})
    assert a1.status_code == 200
    chunks_default = a1.json().get("chunks", [])
    assert isinstance(chunks_default, list)

    # Apply with override (smaller max_size -> likely more chunks)
    a2 = client.post(
        "/api/v1/chunking/templates/apply",
        json={"template_name": tmpl_name, "text": text, "override_options": {"max_size": 10, "overlap": 0}}
    )
    assert a2.status_code == 200
    chunks_override = a2.json().get("chunks", [])
    assert isinstance(chunks_override, list)

    # Prefer different chunk count with override; if equal, still accept successful apply
    if chunks_default and chunks_override:
        assert len(chunks_override) >= len(chunks_default)


def test_validate_rejects_dangerous_boundary_patterns(client_with_media_db: TestClient):
    client = client_with_media_db
    # Dangerous nested-quantifier pattern should be rejected
    payload = {
        "chunking": {
            "method": "sentences",
            "config": {
                "hierarchical": True,
                "hierarchical_template": {
                    "boundaries": [
                        {"kind": "x", "pattern": r"(a+)+b", "flags": "m"}
                    ]
                }
            }
        }
    }
    resp = client.post("/api/v1/chunking/templates/validate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("valid") is False
    msgs = [e.get("message", "").lower() for e in body.get("errors", [])]
    assert any("dangerous" in m or "regex" in m for m in msgs)

    # Safe pattern should pass
    safe_payload = {
        "chunking": {
            "method": "sentences",
            "config": {
                "hierarchical": True,
                "hierarchical_template": {
                    "boundaries": [
                        {"kind": "chapter", "pattern": r"^chapter \d+$", "flags": "im"}
                    ]
                }
            }
        }
    }
    ok = client.post("/api/v1/chunking/templates/validate", json=safe_payload)
    assert ok.status_code == 200
    assert ok.json().get("valid") is True
