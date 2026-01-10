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
