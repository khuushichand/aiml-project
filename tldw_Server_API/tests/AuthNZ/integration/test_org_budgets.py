import pytest

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _user_headers


pytestmark = pytest.mark.integration


def test_org_budgets_get_and_update(isolated_test_environment):
    client, _db_name = isolated_test_environment
    headers = _user_headers(client, suffix="orgbudgets")

    org_resp = client.post("/api/v1/orgs", headers=headers, json={"name": "Org Budgets"})
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    list_resp = client.get(f"/api/v1/orgs/{org_id}/budgets", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    payload = list_resp.json()
    assert payload["org_id"] == org_id

    update_resp = client.post(
        f"/api/v1/orgs/{org_id}/budgets",
        headers=headers,
        json={
            "budgets": {
                "budget_day_usd": 10.0,
            }
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    budgets = update_resp.json()["budgets"]
    assert budgets["budget_day_usd"] == 10.0
    assert budgets["enforcement_mode"]["global"] == "none"
    assert budgets["enforcement_mode"]["per_metric"] == {}


def test_org_budgets_rejects_usd_precision(isolated_test_environment):
    client, _db_name = isolated_test_environment
    headers = _user_headers(client, suffix="orgbudgets-precision")

    org_resp = client.post("/api/v1/orgs", headers=headers, json={"name": "Org Budgets Precision"})
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    update_resp = client.post(
        f"/api/v1/orgs/{org_id}/budgets",
        headers=headers,
        json={
            "budgets": {"budget_month_usd": 9.999},
        },
    )
    assert update_resp.status_code == 422, update_resp.text
