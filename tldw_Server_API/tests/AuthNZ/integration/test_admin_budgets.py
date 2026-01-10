import pytest

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _admin_headers


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
