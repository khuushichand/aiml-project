import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app


pytestmark = pytest.mark.unit


def test_persona_catalog_smoke():
    with TestClient(fastapi_app) as c:
        r = c.get("/api/v1/persona/catalog")
        assert r.status_code == 200
        # Returns empty list if disabled; else list of personas
        assert isinstance(r.json(), list)
