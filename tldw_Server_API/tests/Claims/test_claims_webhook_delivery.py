import json
import types

from tldw_Server_API.app.core.Claims_Extraction import claims_service
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def test_claims_webhook_delivery_retries_and_records(monkeypatch, tmp_path):


    db_path = tmp_path / "media.db"
    db = MediaDatabase(db_path=str(db_path), client_id="test")
    db.initialize_db()
    db.close_connection()

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):

            return False

    class DummyResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    responses = [500, 200]
    delivery_calls = []

    def fake_fetch(*_args, **_kwargs):

        status = responses.pop(0)
        return DummyResponse(status)

    def fake_record_delivery(**kwargs):

        delivery_calls.append(kwargs)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.http_client.create_client",
        lambda **_kwargs: DummyClient(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.http_client.fetch",
        fake_fetch,
    )
    monkeypatch.setattr(claims_service, "record_claims_webhook_delivery", fake_record_delivery)
    monkeypatch.setattr(claims_service.random, "uniform", lambda *_args, **_kwargs: 1.0)
    proxy_time = types.SimpleNamespace(
        time=claims_service.time.time,
        sleep=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(claims_service, "time", proxy_time)

    claims_service._deliver_claims_alert_webhook(
        url="https://example.com/webhook",
        payload={"ok": True},
        channel="webhook",
        db_path=str(db_path),
        user_id="1",
        alert_id=42,
    )

    assert [call["status"] for call in delivery_calls] == ["failure", "success"]

    db = MediaDatabase(db_path=str(db_path), client_id="test")
    rows = db.execute_query(
        "SELECT payload_json FROM claims_monitoring_events ORDER BY id ASC"
    ).fetchall()
    db.close_connection()
    assert len(rows) == 2
    payloads = [json.loads(row["payload_json"]) for row in rows]
    assert payloads[0]["status"] == "failure"
    assert payloads[0]["attempt"] == 1
    assert payloads[1]["status"] == "success"
    assert payloads[1]["attempt"] == 2


def test_claims_webhook_backoff_schedule(monkeypatch, tmp_path):


    db_path = tmp_path / "media.db"
    db = MediaDatabase(db_path=str(db_path), client_id="test")
    db.initialize_db()
    db.close_connection()

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):

            return False

    class DummyResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    def fake_fetch(*_args, **_kwargs):

        return DummyResponse(500)

    sleeps = []

    monkeypatch.setattr(
        "tldw_Server_API.app.core.http_client.create_client",
        lambda **_kwargs: DummyClient(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.http_client.fetch",
        fake_fetch,
    )
    monkeypatch.setattr(claims_service, "record_claims_webhook_delivery", lambda **_kwargs: None)
    monkeypatch.setattr(claims_service.random, "uniform", lambda *_args, **_kwargs: 1.0)
    proxy_time = types.SimpleNamespace(
        time=claims_service.time.time,
        sleep=lambda delay: sleeps.append(delay),
    )
    monkeypatch.setattr(claims_service, "time", proxy_time)

    claims_service._deliver_claims_alert_webhook(
        url="https://example.com/webhook",
        payload={"ok": False},
        channel="webhook",
        db_path=str(db_path),
        user_id="1",
        alert_id=99,
    )

    assert sleeps == [5, 15, 45, 120]

    db = MediaDatabase(db_path=str(db_path), client_id="test")
    row = db.execute_query(
        "SELECT COUNT(*) AS total FROM claims_monitoring_events"
    ).fetchone()
    db.close_connection()
    total = int(row["total"]) if isinstance(row, dict) else int(row[0])
    assert total == 5
