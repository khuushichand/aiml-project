from fastapi.testclient import TestClient


def test_create_note_auto_title_mvp(client_user_only: TestClient):
    r = client_user_only.post(
        "/api/v1/notes/",
        json={
            "content": "# Heading level 1\nBody paragraph.",
            "auto_title": True,
            "title_max_len": 250,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] and len(data["title"]) <= 250


def test_suggest_title_mvp(client_user_only: TestClient):
    r = client_user_only.post(
        "/api/v1/notes/title/suggest",
        json={
            "content": "[Guide](https://example.com) — Intro to Systems.",
            "title_max_len": 64,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["title"] and len(data["title"]) <= 64
