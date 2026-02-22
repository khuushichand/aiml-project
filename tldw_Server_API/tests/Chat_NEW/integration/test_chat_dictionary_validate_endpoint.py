import pytest


@pytest.mark.integration
def test_validate_dictionary_endpoint_success(test_client, auth_headers):
    payload = {
        "data": {
            "name": "test",
            "entries": [
                {"type": "literal", "pattern": "hello", "replacement": "hi"}
            ]
        },
        "schema_version": 1,
        "strict": False,
    }
    r = test_client.post("/api/v1/chat/dictionaries/validate", json=payload, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["schema_version"] == 1
    assert isinstance(data.get("entry_stats"), dict)
    assert isinstance(data.get("errors"), list)
    assert isinstance(data.get("warnings"), list)
    assert data.get("partial") is False
    assert data.get("partial_reason") is None


@pytest.mark.integration
def test_validate_dictionary_endpoint_detects_regex_error(test_client, auth_headers):
    payload = {
        "data": {
            "name": "test-bad",
            "entries": [
                {"type": "regex", "pattern": "(unclosed", "replacement": "x"}
            ]
        },
        "schema_version": 1,
        "strict": False,
    }
    r = test_client.post("/api/v1/chat/dictionaries/validate", json=payload, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    codes = {e.get("code") for e in data.get("errors", [])}
    assert "regex_invalid" in codes


@pytest.mark.integration
def test_validate_dictionary_endpoint_unknown_schema_version_reports_schema_invalid(test_client, auth_headers):
    payload = {
        "data": {
            "name": "test-schema",
            "entries": [
                {"type": "literal", "pattern": "hello", "replacement": "hi"}
            ]
        },
        "schema_version": 999,
        "strict": False,
    }
    r = test_client.post("/api/v1/chat/dictionaries/validate", json=payload, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    codes = {e.get("code") for e in data.get("errors", [])}
    assert "schema_invalid" in codes


@pytest.mark.integration
def test_validate_dictionary_endpoint_partial_max_entries(monkeypatch, test_client, auth_headers):
    monkeypatch.setenv("CHAT_DICT_VALIDATE_MAX_ENTRIES", "1")
    payload = {
        "data": {
            "name": "test-partial",
            "entries": [
                {"type": "literal", "pattern": "a", "replacement": "x"},
                {"type": "literal", "pattern": "b", "replacement": "y"},
            ]
        },
        "schema_version": 1,
        "strict": False,
    }
    r = test_client.post("/api/v1/chat/dictionaries/validate", json=payload, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("partial") is True
    assert data.get("partial_reason") == "max_entries"


@pytest.mark.integration
def test_validate_dictionary_endpoint_requires_auth(test_client):
    payload = {
        "data": {
            "name": "test",
            "entries": [
                {"type": "literal", "pattern": "hello", "replacement": "hi"}
            ]
        },
        "schema_version": 1,
        "strict": False,
    }
    r = test_client.post("/api/v1/chat/dictionaries/validate", json=payload)
    assert r.status_code == 401
