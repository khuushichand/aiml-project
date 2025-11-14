import pytest
from fastapi.testclient import TestClient


def test_create_note_with_auto_title(client_user_only: TestClient):
    resp = client_user_only.post(
        "/api/v1/notes/",
        json={
            "content": "# Heading\nSome content body explaining things.",
            "auto_title": True,
            "title_strategy": "heuristic",
            "title_max_len": 250,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"]
    assert len(data["title"]) <= 250
    assert data["content"].startswith("# Heading") or data["content"].startswith("Heading")


def test_bulk_create_with_auto_title(client_user_only: TestClient):
    payload = {
        "notes": [
            {
                "content": "Intro line\nDetails...",
                "auto_title": True,
                "title_strategy": "heuristic",
                "title_max_len": 250,
            }
        ]
    }
    resp = client_user_only.post("/api/v1/notes/bulk", json=payload)
    assert resp.status_code in (200, 207), resp.text
    data = resp.json()
    assert data["created_count"] >= 1
    assert data["results"][0]["success"] is True
    note = data["results"][0]["note"]
    assert note["title"]
    assert len(note["title"]) <= 250


def test_suggest_title_endpoint(client_user_only: TestClient):
    resp = client_user_only.post(
        "/api/v1/notes/title/suggest",
        json={
            "content": "[Deep Dive](https://example.com) — A long read about AI.\nMore text.",
            "title_strategy": "heuristic",
            "title_max_len": 50,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"]
    assert len(data["title"]) <= 50

