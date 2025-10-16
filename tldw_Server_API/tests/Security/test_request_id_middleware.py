import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Security.request_id_middleware import RequestIDMiddleware, _clean_request_id


@pytest.fixture(scope="module")
def app_with_request_id():
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping(request: Request):
        return {"request_id": request.state.request_id}

    return app


def test_request_id_preserves_clean_value(app_with_request_id):
    client = TestClient(app_with_request_id)
    req_id = "abc-123.DEF"
    resp = client.get("/ping", headers={"X-Request-ID": req_id})
    assert resp.status_code == 200
    assert resp.json()["request_id"] == req_id
    assert resp.headers["X-Request-ID"] == req_id


def test_request_id_rejects_malicious_value(app_with_request_id):
    client = TestClient(app_with_request_id)
    raw = "aaa\nbbb"
    resp = client.get("/ping", headers={"X-Request-ID": raw})
    assert resp.status_code == 200
    generated = resp.headers["X-Request-ID"]
    assert "\n" not in generated
    assert generated != raw
    uuid.UUID(generated)  # Raises if not valid UUID


def test_request_id_rejects_excessive_length(app_with_request_id):
    client = TestClient(app_with_request_id)
    oversized = "a" * 1024
    resp = client.get("/ping", headers={"X-Request-ID": oversized})
    assert resp.status_code == 200
    generated = resp.headers["X-Request-ID"]
    assert len(generated) < len(oversized)
    uuid.UUID(generated)


def test_clean_request_id_generates_when_missing():
    assert uuid.UUID(_clean_request_id(None))
