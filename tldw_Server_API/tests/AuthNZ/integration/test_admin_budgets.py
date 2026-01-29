import asyncio
import json
import threading

import asyncpg
import pytest

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _admin_headers
from tldw_Server_API.tests.helpers.pg_env import get_pg_env


_pg = get_pg_env()
TEST_DB_HOST = _pg.host
TEST_DB_PORT = int(_pg.port)
TEST_DB_USER = _pg.user
TEST_DB_PASSWORD = _pg.password


def _run_async(coro):
    """Run an async coroutine from sync tests, tolerating an active loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {}

    def _runner():
        result["value"] = asyncio.run(coro)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()
    return result.get("value")


async def _set_custom_limits_json(db_name: str, org_id: int, payload: dict) -> None:
    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=db_name,
    )
    try:
        plan_id = await conn.fetchval(
            "SELECT id FROM subscription_plans WHERE name=$1",
            "free",
        )
        if plan_id is None:
            raise RuntimeError("Free plan not found")
        await conn.execute(
            """
            INSERT INTO org_subscriptions (org_id, plan_id, status, custom_limits_json)
            VALUES ($1, $2, 'active', $3::jsonb)
            ON CONFLICT (org_id)
            DO UPDATE SET custom_limits_json = EXCLUDED.custom_limits_json,
                          updated_at = CURRENT_TIMESTAMP
            """,
            org_id,
            plan_id,
            json.dumps(payload),
        )
    finally:
        await conn.close()


async def _fetch_custom_limits_json(db_name: str, org_id: int) -> dict:
    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=db_name,
    )
    try:
        value = await conn.fetchval(
            "SELECT custom_limits_json FROM org_subscriptions WHERE org_id=$1",
            org_id,
        )
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
                if isinstance(decoded, dict):
                    return decoded
            except json.JSONDecodeError:
                pass
        return value
    finally:
        await conn.close()


pytestmark = pytest.mark.integration


def test_admin_budgets_list_and_update(isolated_test_environment):


    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    org_resp = client.post("/api/v1/admin/orgs", headers=headers, json={"name": "Budget Org"})
    assert org_resp.status_code == 200, org_resp.text
    org_id = org_resp.json()["id"]

    list_resp = client.get(f"/api/v1/admin/budgets?org_id={org_id}", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    payload = list_resp.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["org_id"] == org_id

    update_resp = client.post(
        "/api/v1/admin/budgets",
        headers=headers,
        json={
            "org_id": org_id,
            "budgets": {
                "budget_month_usd": 125.0,
                "budget_day_tokens": 50000,
                "alert_thresholds": {
                    "global": [95, 80, 80],
                    "per_metric": {"budget_day_usd": [90]},
                },
                "enforcement_mode": {
                    "global": "soft",
                    "per_metric": {"budget_day_usd": "hard"},
                },
            },
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["org_id"] == org_id
    assert updated["budgets"]["budget_month_usd"] == 125.0
    assert updated["budgets"]["budget_day_tokens"] == 50000
    assert updated["budgets"]["alert_thresholds"]["global"] == [80, 95]
    assert updated["budgets"]["alert_thresholds"]["per_metric"]["budget_day_usd"] == [90]
    assert updated["budgets"]["enforcement_mode"]["global"] == "soft"
    assert updated["budgets"]["enforcement_mode"]["per_metric"]["budget_day_usd"] == "hard"

    verify_resp = client.get(f"/api/v1/admin/budgets?org_id={org_id}", headers=headers)
    assert verify_resp.status_code == 200, verify_resp.text
    budgets = verify_resp.json()["items"][0]["budgets"]
    assert budgets["budget_month_usd"] == 125.0
    assert budgets["budget_day_tokens"] == 50000
    assert budgets["alert_thresholds"]["global"] == [80, 95]
    assert budgets["alert_thresholds"]["per_metric"]["budget_day_usd"] == [90]
    assert budgets["enforcement_mode"]["global"] == "soft"
    assert budgets["enforcement_mode"]["per_metric"]["budget_day_usd"] == "hard"


def test_admin_budgets_defaults_in_response(isolated_test_environment):
    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    org_resp = client.post("/api/v1/admin/orgs", headers=headers, json={"name": "Defaults Org"})
    assert org_resp.status_code == 200, org_resp.text
    org_id = org_resp.json()["id"]

    update_resp = client.post(
        "/api/v1/admin/budgets",
        headers=headers,
        json={
            "org_id": org_id,
            "budgets": {
                "budget_month_usd": 75.0,
                "alert_thresholds": {"global": [80]},
            },
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    budgets = update_resp.json()["budgets"]
    assert budgets["budget_month_usd"] == 75.0
    assert budgets["alert_thresholds"]["global"] == [80]
    assert budgets["alert_thresholds"]["per_metric"] == {}
    assert budgets["enforcement_mode"]["global"] == "none"
    assert budgets["enforcement_mode"]["per_metric"] == {}


def test_admin_budgets_rejects_usd_precision(isolated_test_environment):
    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    org_resp = client.post("/api/v1/admin/orgs", headers=headers, json={"name": "Precision Org"})
    assert org_resp.status_code == 200, org_resp.text
    org_id = org_resp.json()["id"]

    update_resp = client.post(
        "/api/v1/admin/budgets",
        headers=headers,
        json={
            "org_id": org_id,
            "budgets": {"budget_day_usd": 10.123},
        },
    )
    assert update_resp.status_code == 422, update_resp.text


def test_admin_budgets_update_does_not_mutate_custom_limits_json(isolated_test_environment):
    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    org_resp = client.post("/api/v1/admin/orgs", headers=headers, json={"name": "Custom Limits Org"})
    assert org_resp.status_code == 200, org_resp.text
    org_id = org_resp.json()["id"]

    custom_limits = {
        "budgets": {"budget_day_usd": 5.0},
        "feature_limit": 3,
    }
    _run_async(_set_custom_limits_json(db_name, org_id, custom_limits))
    before = _run_async(_fetch_custom_limits_json(db_name, org_id))
    assert before == custom_limits

    update_resp = client.post(
        "/api/v1/admin/budgets",
        headers=headers,
        json={
            "org_id": org_id,
            "budgets": {"budget_month_usd": 200.0},
        },
    )
    assert update_resp.status_code == 200, update_resp.text

    after = _run_async(_fetch_custom_limits_json(db_name, org_id))
    assert after == custom_limits


def test_admin_budget_audit_failure_blocks_update(isolated_test_environment, monkeypatch):
    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    org_resp = client.post("/api/v1/admin/orgs", headers=headers, json={"name": "Audit Org"})
    assert org_resp.status_code == 200, org_resp.text
    org_id = org_resp.json()["id"]

    first_resp = client.post(
        "/api/v1/admin/budgets",
        headers=headers,
        json={
            "org_id": org_id,
            "budgets": {"budget_month_usd": 100.0},
        },
    )
    assert first_resp.status_code == 200, first_resp.text

    async def _fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit down")

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.admin.emit_budget_audit_event",
        _fail_audit,
    )

    failed_resp = client.post(
        "/api/v1/admin/budgets",
        headers=headers,
        json={
            "org_id": org_id,
            "budgets": {"budget_month_usd": 200.0},
        },
    )
    assert failed_resp.status_code == 500, failed_resp.text
    assert failed_resp.json()["detail"] == "audit_failed"
