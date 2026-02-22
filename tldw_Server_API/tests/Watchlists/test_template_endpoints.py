"""Tests for /templates/validate and /templates/preview endpoints.

Covers: syntax validation, error sanitization, live preview rendering,
and edge cases (empty template, missing run, no items).
"""

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=990, username="tmpluser", email="tmpl@example.com", is_active=True)

    base_dir = tmp_path / "test_user_dbs_template_endpoints"
    base_dir.mkdir(parents=True, exist_ok=True)
    template_dir = tmp_path / "watchlist_templates"
    template_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WATCHLIST_TEMPLATE_DIR", str(template_dir))
    monkeypatch.setenv("WATCHLISTS_SEED_OUTPUT_TEMPLATES", "false")
    monkeypatch.setenv("TEST_MODE", "1")

    from fastapi import FastAPI
    from tldw_Server_API.app.core.config import API_V1_PREFIX
    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ── Validate endpoint ────────────────────────────────────────────────


class TestValidateTemplate:
    def test_valid_template(self, client_with_user: TestClient):
        """Valid Jinja2 returns valid=True, no errors."""
        r = client_with_user.post(
            "/api/v1/watchlists/templates/validate",
            json={"content": "Hello {{ name }}", "format": "md"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["valid"] is True
        assert body["errors"] == []

    def test_invalid_template(self, client_with_user: TestClient):
        """Broken Jinja2 syntax returns valid=False with error details."""
        r = client_with_user.post(
            "/api/v1/watchlists/templates/validate",
            json={"content": "{% for x in items %}", "format": "md"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["valid"] is False
        assert len(body["errors"]) >= 1
        assert body["errors"][0]["message"]

    def test_empty_template_is_valid(self, client_with_user: TestClient):
        """Empty string is syntactically valid Jinja2."""
        r = client_with_user.post(
            "/api/v1/watchlists/templates/validate",
            json={"content": "", "format": "md"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["valid"] is True
        assert body["errors"] == []

    def test_error_message_sanitized(self, client_with_user: TestClient, monkeypatch):
        """Unexpected validation error does not leak internals."""
        from jinja2.sandbox import SandboxedEnvironment

        original_init = SandboxedEnvironment.__init__

        def explode(*args, **kwargs):
            original_init(*args, **kwargs)
            raise RuntimeError("/some/internal/path/leaked")

        monkeypatch.setattr(SandboxedEnvironment, "__init__", explode)

        r = client_with_user.post(
            "/api/v1/watchlists/templates/validate",
            json={"content": "{{ hello }}", "format": "md"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["valid"] is False
        assert len(body["errors"]) == 1
        # Must NOT contain internal paths
        assert "/some/internal/path" not in body["errors"][0]["message"]
        assert "internal error" in body["errors"][0]["message"].lower()

    def test_valid_html_template(self, client_with_user: TestClient):
        """HTML-format templates validate correctly."""
        r = client_with_user.post(
            "/api/v1/watchlists/templates/validate",
            json={"content": "<h1>{{ title }}</h1>{% for i in items %}<p>{{ i.name }}</p>{% endfor %}", "format": "html"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["valid"] is True


# ── Preview endpoint ─────────────────────────────────────────────────


def _create_run(c: TestClient) -> int:
    """Helper to create a source → job → run for preview tests."""
    source = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "TestFeed", "url": "https://example.com/rss.xml", "source_type": "rss"},
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["id"]

    job = c.post(
        "/api/v1/watchlists/jobs",
        json={"name": "PreviewJob", "scope": {"sources": [source_id]}, "active": True},
    )
    assert job.status_code == 200, job.text
    job_id = job.json()["id"]

    run = c.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert run.status_code == 200, run.text
    return run.json()["id"]


class TestPreviewTemplate:
    def test_preview_run_not_found(self, client_with_user: TestClient):
        """Non-existent run_id returns 404."""
        r = client_with_user.post(
            "/api/v1/watchlists/templates/preview",
            json={"content": "{{ title }}", "format": "md", "run_id": 999999},
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "run_not_found"

    def test_preview_returns_rendered(self, client_with_user: TestClient):
        """Run with items returns rendered output and context keys."""
        run_id = _create_run(client_with_user)
        r = client_with_user.post(
            "/api/v1/watchlists/templates/preview",
            json={"content": "# {{ title }}\nItems: {{ item_count }}", "format": "md", "run_id": run_id},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "rendered" in body
        assert "title" in body.get("context_keys", [])
        assert "item_count" in body.get("context_keys", [])
        assert body["warnings"] == []

    def test_preview_render_error_sanitized(self, client_with_user: TestClient, monkeypatch):
        """Render error in preview returns a generic warning, not internals."""
        run_id = _create_run(client_with_user)

        # Force the template renderer to raise
        import tldw_Server_API.app.api.v1.endpoints.watchlists as wl_mod
        original = wl_mod._render_template_with_context

        def exploding_render(template_str, context):
            raise RuntimeError("/internal/path/secret")

        monkeypatch.setattr(wl_mod, "_render_template_with_context", exploding_render)

        r = client_with_user.post(
            "/api/v1/watchlists/templates/preview",
            json={"content": "{{ title }}", "format": "md", "run_id": run_id},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["warnings"]) >= 1
        assert body["warnings"][0] == "Template rendering failed"
        # Must NOT leak internals
        assert "/internal/path" not in str(body["warnings"])
