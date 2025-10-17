import pytest


@pytest.mark.e2e
def test_workflow_posts_include_csrf_header(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.wait_for_function("() => window.apiClient && window.apiClient.baseUrl")

    # Prime CSRF cookie by performing an authenticated GET
    page.evaluate("() => window.apiClient.get('/api/v1/workflows')")
    page.wait_for_timeout(200)

    definition = {
        "name": "playwright-csrf-check",
        "version": 1,
        "steps": [
            {
                "id": "s1",
                "type": "prompt",
                "config": {"template": "Hello from Playwright"},
            }
        ],
    }

    with page.expect_request(
        lambda req: req.url.endswith("/api/v1/workflows") and req.method == "POST"
    ) as create_request_info:
        create_resp = page.evaluate(
            "definition => window.apiClient.post('/api/v1/workflows', definition)",
            definition,
        )

    create_request = create_request_info.value
    csrf_header = create_request.headers.get("x-csrf-token")
    assert csrf_header, "Expected X-CSRF-Token header on workflow create request"

    csrf_cookie = next(
        (cookie["value"] for cookie in page.context.cookies() if cookie["name"] == "csrf_token"),
        None,
    )
    assert csrf_cookie, "Expected csrf_token cookie to be present after workflow create"
    assert csrf_header == csrf_cookie, "Header token should match csrf_token cookie"

    workflow_id = create_resp["id"]

    run_payload = {"inputs": {"name": "CSRF"}}
    with page.expect_request(
        lambda req: f"/api/v1/workflows/{workflow_id}/run" in req.url and req.method == "POST"
    ) as run_request_info:
        page.evaluate(
            """({workflowId, payload}) =>
                window.apiClient.post(`/api/v1/workflows/${workflowId}/run`, payload)
            """,
            {"workflowId": workflow_id, "payload": run_payload},
        )

    run_request = run_request_info.value
    run_csrf_header = run_request.headers.get("x-csrf-token")
    assert run_csrf_header, "Expected X-CSRF-Token header on workflow run request"

    latest_cookie = next(
        (cookie["value"] for cookie in page.context.cookies() if cookie["name"] == "csrf_token"),
        None,
    )
    assert latest_cookie, "Expected csrf_token cookie to remain set after workflow run"
    assert (
        run_csrf_header == latest_cookie
    ), "Run request should reuse the current csrf_token value"
