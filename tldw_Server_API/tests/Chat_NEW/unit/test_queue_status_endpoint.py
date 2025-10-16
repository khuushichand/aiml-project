import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


class _QStub:
    def get_queue_status(self):
        return {
            "queue_size": 1,
            "processing_count": 0,
            "max_queue_size": 100,
            "max_concurrent": 4,
            "total_processed": 10,
            "total_rejected": 2,
            "is_running": True,
        }


@pytest.mark.unit
def test_queue_status_endpoint_enabled():
    with TestClient(app) as client:
        with patch("tldw_Server_API.app.api.v1.endpoints.chat.get_request_queue", return_value=_QStub()):
            resp = client.get("/api/v1/chat/queue/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("enabled") is True
            assert data.get("queue_size") == 1

@pytest.mark.unit
def test_queue_status_endpoint_disabled():
    with TestClient(app) as client:
        with patch("tldw_Server_API.app.api.v1.endpoints.chat.get_request_queue", return_value=None):
            resp = client.get("/api/v1/chat/queue/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("enabled") is False
