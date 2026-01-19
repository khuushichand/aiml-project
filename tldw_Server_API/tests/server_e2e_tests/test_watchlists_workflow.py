import os
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


@pytest.mark.e2e
def test_watchlists_sources_jobs_runs_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    tag_name = f"watchlist-{suffix}"

    group_resp = page.request.post(
        "/api/v1/watchlists/groups",
        headers=headers,
        json={"name": f"E2E Group {suffix}", "description": "E2E watchlists group"},
    )
    _require_ok(group_resp, "create group")
    group_id = group_resp.json()["id"]

    groups_resp = page.request.get("/api/v1/watchlists/groups", headers=headers)
    _require_ok(groups_resp, "list groups")
    assert any(item.get("id") == group_id for item in groups_resp.json().get("items", []))

    source_resp = page.request.post(
        "/api/v1/watchlists/sources",
        headers=headers,
        json={
            "name": f"E2E Source {suffix}",
            "url": f"{server_url}/docs",
            "source_type": "site",
            "active": True,
            "tags": [tag_name],
            "group_ids": [group_id],
            "settings": {"top_n": 1},
        },
    )
    _require_ok(source_resp, "create source")
    source_payload = source_resp.json()
    source_id = source_payload["id"]

    tags_resp = page.request.get("/api/v1/watchlists/tags", headers=headers)
    _require_ok(tags_resp, "list tags")
    assert any(item.get("name") == tag_name for item in tags_resp.json().get("items", []))

    sources_resp = page.request.get(
        "/api/v1/watchlists/sources",
        headers=headers,
        params={"tags": tag_name, "page": 1, "size": 50},
    )
    _require_ok(sources_resp, "list sources")
    assert any(item.get("id") == source_id for item in sources_resp.json().get("items", []))

    get_source_resp = page.request.get(f"/api/v1/watchlists/sources/{source_id}", headers=headers)
    _require_ok(get_source_resp, "get source")
    assert get_source_resp.json()["id"] == source_id

    test_source_resp = page.request.post(
        f"/api/v1/watchlists/sources/{source_id}/test",
        headers=headers,
        params={"limit": 5},
    )
    _require_ok(test_source_resp, "test source")
    test_payload = test_source_resp.json()
    assert test_payload.get("total", 0) >= 1

    job_resp = page.request.post(
        "/api/v1/watchlists/jobs",
        headers=headers,
        json={
            "name": f"E2E Job {suffix}",
            "description": "E2E watchlists job",
            "scope": {"sources": [source_id]},
            "active": True,
            "job_filters": {
                "filters": [
                    {"type": "keyword", "action": "flag", "value": {"keywords": ["Test"]}},
                ]
            },
        },
    )
    _require_ok(job_resp, "create job")
    job_payload = job_resp.json()
    job_id = job_payload["id"]

    get_job_resp = page.request.get(f"/api/v1/watchlists/jobs/{job_id}", headers=headers)
    _require_ok(get_job_resp, "get job")
    assert get_job_resp.json()["id"] == job_id

    update_job_resp = page.request.patch(
        f"/api/v1/watchlists/jobs/{job_id}",
        headers=headers,
        json={"description": f"Updated job {suffix}"},
    )
    _require_ok(update_job_resp, "update job")
    assert update_job_resp.json()["description"] == f"Updated job {suffix}"

    preview_job_resp = page.request.post(
        f"/api/v1/watchlists/jobs/{job_id}/preview",
        headers=headers,
        params={"limit": 5},
    )
    _require_ok(preview_job_resp, "preview job")
    preview_payload = preview_job_resp.json()
    assert preview_payload.get("total", 0) >= 1

    run_resp = page.request.post(
        f"/api/v1/watchlists/jobs/{job_id}/run",
        headers=headers,
    )
    _require_ok(run_resp, "trigger run")
    run_payload = run_resp.json()
    run_id = run_payload["id"]

    run_get_resp = page.request.get(f"/api/v1/watchlists/runs/{run_id}", headers=headers)
    _require_ok(run_get_resp, "get run")
    assert run_get_resp.json()["id"] == run_id

    run_details_resp = page.request.get(
        f"/api/v1/watchlists/runs/{run_id}/details",
        headers=headers,
        params={"include_tallies": "true"},
    )
    _require_ok(run_details_resp, "get run details")

    runs_for_job_resp = page.request.get(
        f"/api/v1/watchlists/jobs/{job_id}/runs",
        headers=headers,
        params={"page": 1, "size": 50},
    )
    _require_ok(runs_for_job_resp, "list runs for job")
    assert any(item.get("id") == run_id for item in runs_for_job_resp.json().get("items", []))

    runs_global_resp = page.request.get(
        "/api/v1/watchlists/runs",
        headers=headers,
        params={"page": 1, "size": 50},
    )
    _require_ok(runs_global_resp, "list runs global")
    assert any(item.get("id") == run_id for item in runs_global_resp.json().get("items", []))

    csv_resp = page.request.get(
        "/api/v1/watchlists/runs/export.csv",
        headers=headers,
        params={"scope": "job", "job_id": job_id},
    )
    _require_ok(csv_resp, "export runs csv")
    csv_text = csv_resp.text()
    assert "id,job_id,status" in csv_text.splitlines()[0]

    items_resp = page.request.get(
        "/api/v1/watchlists/items",
        headers=headers,
        params={"run_id": run_id, "page": 1, "size": 50},
    )
    _require_ok(items_resp, "list scraped items")
    items_payload = items_resp.json()
    assert items_payload.get("items")
    item_id = items_payload["items"][0]["id"]

    update_item_resp = page.request.patch(
        f"/api/v1/watchlists/items/{item_id}",
        headers=headers,
        json={"reviewed": True, "status": "reviewed"},
    )
    _require_ok(update_item_resp, "update scraped item")
    assert update_item_resp.json()["reviewed"] is True

    get_item_resp = page.request.get(
        f"/api/v1/watchlists/items/{item_id}",
        headers=headers,
    )
    _require_ok(get_item_resp, "get scraped item")
    assert get_item_resp.json()["id"] == item_id

    delete_job_resp = page.request.delete(
        f"/api/v1/watchlists/jobs/{job_id}",
        headers=headers,
    )
    _require_ok(delete_job_resp, "delete job")

    delete_source_resp = page.request.delete(
        f"/api/v1/watchlists/sources/{source_id}",
        headers=headers,
    )
    _require_ok(delete_source_resp, "delete source")

    delete_group_resp = page.request.delete(
        f"/api/v1/watchlists/groups/{group_id}",
        headers=headers,
    )
    _require_ok(delete_group_resp, "delete group")
