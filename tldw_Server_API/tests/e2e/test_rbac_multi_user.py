"""
test_rbac_multi_user.py
E2E tests for Multi-User and RBAC enforcement.

Covers:
- Non-admin cannot access admin endpoints
- Admin bearer can access admin endpoints and manage registration codes
- Multi-user data isolation across media retrieval and search (and optionally RAG)
- Embedding jobs are isolated per user
- Self virtual API key allows authenticated access via X-API-KEY
"""

import os
import time
import uuid
from typing import Dict, Any, List

import httpx
import pytest

from fixtures import APIClient, create_test_file, cleanup_test_file, AssertionHelpers


def _require_multi_user(api_client: APIClient):
    info = api_client.health_check()
    mode_env = os.getenv("AUTH_MODE", "").lower()
    if (info.get("auth_mode") or mode_env) not in {"multi_user", "multi-user", "multiuser"}:
        pytest.skip("Not in multi_user mode")


class TestRBACAdminAccess:
    """RBAC admin access tests."""

    def test_01_non_admin_forbidden_admin_routes(self, api_client):
        _require_multi_user(api_client)
        # Register and login a regular user
        creds = {
            "username": f"e2e_rbac_user_{int(time.time())}",
            "email": f"e2e_rbac_{uuid.uuid4().hex[:8]}@example.com",
            "password": "Password123!",
        }
        try:
            api_client.register(**creds)
        except httpx.HTTPStatusError:
            pass
        api_client.login(creds["username"], creds["password"])  # sets Authorization header

        # Non-admin should get 403 on admin routes
        r = api_client.client.get("/api/v1/admin/users")
        assert r.status_code == 403

        rc = api_client.client.post(
            "/api/v1/admin/registration-codes",
            json={"max_uses": 1, "expiry_days": 7, "role_to_grant": "user"},
        )
        assert rc.status_code == 403

    def test_02_admin_bearer_can_access_admin_endpoints(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping admin positive tests")

        headers = {"Authorization": f"Bearer {admin_token}"}
        r1 = api_client.client.get("/api/v1/admin/users", headers=headers)
        assert r1.status_code == 200
        assert "users" in r1.json()

        r2 = api_client.client.get("/api/v1/admin/roles", headers=headers)
        assert r2.status_code == 200

        r3 = api_client.client.get("/api/v1/admin/permissions", headers=headers)
        assert r3.status_code == 200

    def test_03_admin_registration_codes_crud(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping registration code CRUD")

        headers = {"Authorization": f"Bearer {admin_token}"}

        # Create
        create = api_client.client.post(
            "/api/v1/admin/registration-codes",
            json={
                "max_uses": 3,
                "expiry_days": 7,
                "role_to_grant": "user",
                "metadata": {"e2e": True},
            },
            headers=headers,
        )
        assert create.status_code == 200, create.text
        code_obj = create.json()
        assert code_obj.get("code") and code_obj.get("id")

        # List
        listing = api_client.client.get("/api/v1/admin/registration-codes", headers=headers)
        assert listing.status_code == 200
        found_ids = [c.get("id") for c in listing.json().get("codes", [])]
        assert code_obj["id"] in found_ids

        # Delete
        delete = api_client.client.delete(
            f"/api/v1/admin/registration-codes/{code_obj['id']}", headers=headers
        )
        assert delete.status_code in (200, 204)


class TestMultiUserIsolation:
    """Verify strict isolation across users for media/search/embeddings jobs."""

    def _poll_embeddings_ready(self, client: APIClient, media_id: int, timeout_s: int = 15) -> bool:
        start = time.time()
        while time.time() - start < timeout_s:
            try:
                r = client.client.get(f"/api/v1/media/{media_id}/embeddings/status")
                if r.status_code == 200 and r.json().get("has_embeddings"):
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def test_10_isolation_media_retrieval_and_search(self):
        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        client_a = APIClient(base)
        client_b = APIClient(base)

        _require_multi_user(client_a)

        # Create user A
        ua = {
            "username": f"userA_{int(time.time())}",
            "email": f"userA_{uuid.uuid4().hex[:6]}@ex.com",
            "password": "Password123!",
        }
        try:
            client_a.register(**ua)
        except httpx.HTTPStatusError:
            pass
        client_a.login(ua["username"], ua["password"])  # Bearer for A

        # Create user B
        ub = {
            "username": f"userB_{int(time.time())}",
            "email": f"userB_{uuid.uuid4().hex[:6]}@ex.com",
            "password": "Password123!",
        }
        try:
            client_b.register(**ub)
        except httpx.HTTPStatusError:
            pass
        client_b.login(ub["username"], ub["password"])  # Bearer for B

        # User A uploads media
        token = f"RBAC_A_TOKEN_{uuid.uuid4().hex[:8]}"
        fp = create_test_file(f"owned by A; token={token}")
        try:
            up = client_a.upload_media(file_path=fp, title="A Doc", media_type="document", generate_embeddings=False)
            mid = AssertionHelpers.assert_successful_upload(up)

            # User B cannot retrieve user A's media by id
            r_forbidden = client_b.client.get(f"/api/v1/media/{mid}")
            assert r_forbidden.status_code in (403, 404)

            # User B text search for token should not surface A's media
            sr_b = client_b.client.post("/api/v1/media/search", json={"query": token}, params={"limit": 10})
            if sr_b.status_code == 200:
                results = sr_b.json() if isinstance(sr_b.json(), list) else sr_b.json().get("results", [])
                ids = [(x.get("id") or x.get("media_id")) for x in results]
                assert mid not in ids

            # Optional: RAG isolation (if available)
            try:
                # Generate embeddings for A, then search as B
                gen = client_a.client.post(f"/api/v1/media/{mid}/embeddings", json={})
                assert gen.status_code == 200
                self._poll_embeddings_ready(client_a, mid, timeout_s=15)
                rag_b = client_b.client.post(
                    "/api/v1/rag/search/simple", json={"query": token, "databases": ["media"], "top_k": 5}
                )
                if rag_b.status_code == 200 and isinstance(rag_b.json(), dict):
                    items = rag_b.json().get("results", [])
                    ids = []
                    for it in items:
                        src = it.get("source") or {}
                        ids.append(src.get("id") or src.get("media_id"))
                    assert mid not in ids
            except httpx.HTTPStatusError:
                # RAG may be disabled; skip
                pass
        finally:
            cleanup_test_file(fp)

    def test_11_isolation_embedding_jobs(self):
        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        client_a = APIClient(base)
        client_b = APIClient(base)
        _require_multi_user(client_a)

        # Login/register both users
        n = int(time.time())
        ua = {"username": f"userA_jobs_{n}", "email": f"userA_jobs_{n}@ex.com", "password": "Password123!"}
        ub = {"username": f"userB_jobs_{n}", "email": f"userB_jobs_{n}@ex.com", "password": "Password123!"}
        for c, creds in ((client_a, ua), (client_b, ub)):
            try:
                c.register(**creds)
            except httpx.HTTPStatusError:
                pass
            c.login(creds["username"], creds["password"])  # sets bearer

        # User A uploads and triggers embeddings
        fp = create_test_file("jobs owner A")
        try:
            up = client_a.upload_media(file_path=fp, title="Jobs Doc", media_type="document", generate_embeddings=False)
            mid = AssertionHelpers.assert_successful_upload(up)
            gen = client_a.client.post(f"/api/v1/media/{mid}/embeddings", json={})
            assert gen.status_code == 200
            job_info = gen.json()
            job_id = job_info.get("job_id")

            # List jobs as A
            jobs_a = client_a.client.get("/api/v1/media/embeddings/jobs")
            assert jobs_a.status_code == 200
            items_a = jobs_a.json().get("data", []) if isinstance(jobs_a.json(), dict) else []
            a_ids = {j.get("job_id") or j.get("id") for j in items_a}
            assert not job_id or (job_id in a_ids)

            # List jobs as B and ensure A's job is not there
            jobs_b = client_b.client.get("/api/v1/media/embeddings/jobs")
            assert jobs_b.status_code == 200
            items_b = jobs_b.json().get("data", []) if isinstance(jobs_b.json(), dict) else []
            b_ids = {j.get("job_id") or j.get("id") for j in items_b}
            if job_id:
                assert job_id not in b_ids
        finally:
            cleanup_test_file(fp)

    def test_12_self_virtual_key_access(self):
        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        c = APIClient(base)
        _require_multi_user(c)

        creds = {"username": f"vk_{int(time.time())}", "email": f"vk_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            c.register(**creds)
        except httpx.HTTPStatusError:
            pass
        c.login(creds["username"], creds["password"])  # Bearer

        # Create self virtual API key allowing media endpoints
        vk = c.client.post(
            "/api/v1/users/api-keys/virtual",
            json={"name": "e2e-virtual", "allowed_paths": ["/api/v1/media"], "expires_in_days": 7},
        )
        assert vk.status_code in (200, 201), vk.text
        key = vk.json().get("key")
        assert key, vk.text

        # Use X-API-KEY only to access a protected route (media list)
        with httpx.Client(base_url=base, timeout=30) as hc:
            r = hc.get("/api/v1/media/", headers={"X-API-KEY": key})
            assert r.status_code == 200
            data = r.json()
            assert isinstance(data, dict)
            # Structure may vary; just ensure we have a response payload without 401/403


class TestAdminMintedVirtualKeyConstraints:
    """Admin mints constrained virtual key for another user and validates enforcement."""

    def test_20_admin_mints_key_with_allowed_paths_and_methods(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping admin-minted key tests")

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        # Target user
        user = APIClient(base)
        creds = {"username": f"vk_admin_{int(time.time())}", "email": f"vk_admin_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            user.register(**creds)
        except httpx.HTTPStatusError:
            pass
        user.login(creds["username"], creds["password"])  # for me endpoint
        uinfo = user.get_current_user()
        uid = uinfo.get("id") or uinfo.get("user_id")
        assert isinstance(uid, int)

        headers = {"Authorization": f"Bearer {admin_token}"}
        # Mint key limited to rag path and POST method
        mk = api_client.client.post(
            f"/api/v1/admin/users/{uid}/virtual-keys",
            json={
                "name": "vk-rag-only",
                "expires_in_days": 1,
                "allowed_paths": ["/api/v1/rag"],
                "allowed_methods": ["POST"],
            },
            headers=headers,
        )
        assert mk.status_code == 200, mk.text
        key = mk.json().get("key")
        assert key, mk.text

        # Allowed: POST rag simple search
        r_ok = user.client.post(
            "/api/v1/rag/search/simple",
            json={"query": "test", "databases": ["media"], "top_k": 1},
            headers={"X-API-KEY": key},
        )
        assert r_ok.status_code in (200, 404), r_ok.text  # Accept 404 if RAG not wired, but not 401/403
        assert r_ok.status_code not in (401, 403)

        # Forbidden by path: chat not permitted
        r_forbid_path = user.client.post(
            "/api/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}], "model": "noop"},
            headers={"X-API-KEY": key},
        )
        assert r_forbid_path.status_code in (401, 403)

        # Forbidden by method: GET on rag path
        r_forbid_method = user.client.get(
            "/api/v1/rag/search/simple",
            headers={"X-API-KEY": key},
        )
        assert r_forbid_method.status_code in (401, 403, 405)

    def test_21_virtual_key_org_team_metadata_propagation(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping org/team metadata propagation test")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        u = APIClient(base)
        creds = {"username": f"vk_scope_{int(time.time())}", "email": f"vk_scope_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            u.register(**creds)
        except httpx.HTTPStatusError:
            pass
        u.login(creds["username"], creds["password"])  # bearer for /auth/me
        uid = u.get_current_user().get("id")

        # Create org + team for scoping
        org = api_client.client.post("/api/v1/admin/orgs", json={"name": f"VK Org {uuid.uuid4().hex[:6]}"}, headers=headers)
        assert org.status_code == 200, org.text
        org_id = org.json().get("id")

        team = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/teams",
            json={"name": f"VK Team {uuid.uuid4().hex[:4]}"},
            headers=headers,
        )
        assert team.status_code == 200, team.text
        team_id = team.json().get("id")

        # Add the user to org (and optionally team)
        add_org = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=headers,
        )
        assert add_org.status_code == 200, add_org.text

        # Mint a virtual key scoped with org_id/team_id
        mk = api_client.client.post(
            f"/api/v1/admin/users/{uid}/virtual-keys",
            json={
                "name": "vk-org-team-scoped",
                "expires_in_days": 1,
                "org_id": org_id,
                "team_id": team_id,
                "allowed_paths": ["/api/v1/rag"],
                "allowed_methods": ["POST"],
            },
            headers=headers,
        )
        assert mk.status_code == 200, mk.text
        key_id = mk.json().get("id")
        key_val = mk.json().get("key")
        assert key_id and key_val

        # The audit log should reflect org_id/team_id propagation in details
        log = api_client.client.get(f"/api/v1/admin/api-keys/{key_id}/audit-log", headers=headers)
        assert log.status_code == 200, log.text
        entries = log.json().get("items", [])
        assert isinstance(entries, list) and entries, "No audit entries found for new key"
        # Find creation entry
        created = next((e for e in entries if (e.get("action") or "").startswith("created")), entries[0])
        details = created.get("details")
        # details may be a JSON string or dict
        if isinstance(details, str):
            try:
                import json as _json
                details = _json.loads(details)
            except Exception:
                details = {}
        assert isinstance(details, dict)
        # org_id/team_id are expected in details for created_virtual
        assert details.get("org_id") == org_id
        # team_id could be None if not stored; accept equality or None when unsupported
        if team_id is not None:
            assert details.get("team_id") == team_id
        # Allowed endpoints list recorded in audit (may be empty if not set)
        if "allowed_endpoints" in details:
            assert isinstance(details["allowed_endpoints"], list)
        # We cannot directly introspect metadata.allowed_paths here; enforcement is validated elsewhere

    def test_22_virtual_key_org_only_propagation(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping org-only propagation test")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        u = APIClient(base)
        creds = {"username": f"vk_org_only_{int(time.time())}", "email": f"vk_org_only_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            u.register(**creds)
        except httpx.HTTPStatusError:
            pass
        u.login(creds["username"], creds["password"])  # bearer for /auth/me
        uid = u.get_current_user().get("id")

        # Create org only
        org = api_client.client.post("/api/v1/admin/orgs", json={"name": f"VK OrgOnly {uuid.uuid4().hex[:6]}"}, headers=headers)
        assert org.status_code == 200, org.text
        org_id = org.json().get("id")

        # Mint key with only org_id
        mk = api_client.client.post(
            f"/api/v1/admin/users/{uid}/virtual-keys",
            json={"name": "vk-org-only", "expires_in_days": 1, "org_id": org_id},
            headers=headers,
        )
        assert mk.status_code == 200, mk.text
        key_id = mk.json().get("id")
        assert key_id

        log = api_client.client.get(f"/api/v1/admin/api-keys/{key_id}/audit-log", headers=headers)
        assert log.status_code == 200
        items = log.json().get("items", [])
        assert items
        created = next((e for e in items if (e.get("action") or "").startswith("created")), items[0])
        details = created.get("details")
        if isinstance(details, str):
            try:
                import json as _json
                details = _json.loads(details)
            except Exception:
                details = {}
        assert isinstance(details, dict)
        assert details.get("org_id") == org_id
        # team_id may be absent or None
        assert ("team_id" not in details) or details.get("team_id") is None

    def test_23_virtual_key_team_only_propagation(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping team-only propagation test")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        u = APIClient(base)
        creds = {"username": f"vk_team_only_{int(time.time())}", "email": f"vk_team_only_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            u.register(**creds)
        except httpx.HTTPStatusError:
            pass
        u.login(creds["username"], creds["password"])  # bearer for /auth/me
        uid = u.get_current_user().get("id")

        # Create org + team
        org = api_client.client.post("/api/v1/admin/orgs", json={"name": f"VK OrgForTeam {uuid.uuid4().hex[:6]}"}, headers=headers)
        assert org.status_code == 200, org.text
        org_id = org.json().get("id")
        team = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/teams",
            json={"name": f"VK TeamOnly {uuid.uuid4().hex[:4]}"},
            headers=headers,
        )
        assert team.status_code == 200, team.text
        team_id = team.json().get("id")

        # Mint key with only team_id
        mk = api_client.client.post(
            f"/api/v1/admin/users/{uid}/virtual-keys",
            json={"name": "vk-team-only", "expires_in_days": 1, "team_id": team_id},
            headers=headers,
        )
        assert mk.status_code == 200, mk.text
        key_id = mk.json().get("id")
        assert key_id

        log = api_client.client.get(f"/api/v1/admin/api-keys/{key_id}/audit-log", headers=headers)
        assert log.status_code == 200
        items = log.json().get("items", [])
        assert items
        created = next((e for e in items if (e.get("action") or "").startswith("created")), items[0])
        details = created.get("details")
        if isinstance(details, str):
            try:
                import json as _json
                details = _json.loads(details)
            except Exception:
                details = {}
        assert isinstance(details, dict)
        # org_id may be None; team_id should be present
        assert details.get("team_id") == team_id

    def test_24_virtual_key_path_mismatch_blocks_audio_and_chat(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping path mismatch tests")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        u = APIClient(base)
        creds = {"username": f"vk_mismatch_{int(time.time())}", "email": f"vk_mismatch_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            u.register(**creds)
        except httpx.HTTPStatusError:
            pass
        u.login(creds["username"], creds["password"])  # bearer for /auth/me
        uid = u.get_current_user().get("id")

        # Mint key only for rag path
        mk = api_client.client.post(
            f"/api/v1/admin/users/{uid}/virtual-keys",
            json={"name": "vk-rag-only", "expires_in_days": 1, "allowed_paths": ["/api/v1/rag"], "allowed_methods": ["POST"]},
            headers=headers,
        )
        assert mk.status_code == 200, mk.text
        key = mk.json().get("key")
        assert key

        # Chat should be blocked (path not allowed)
        r_chat = u.client.post(
            "/api/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}], "model": "noop"},
            headers={"X-API-KEY": key},
        )
        assert r_chat.status_code in (401, 403)

        # Audio TTS should be blocked (path not allowed)
        r_tts = u.client.post(
            "/api/v1/audio/speech",
            json={"model": "tts-1", "input": "hello world", "voice": "alloy", "response_format": "mp3"},
            headers={"X-API-KEY": key},
        )
        assert r_tts.status_code in (401, 403)

    def test_25_team_scoped_key_non_member_access_patterns(self, api_client):
        """Team-scoped API key for a user not in the team: endpoints that rely on team membership use JWT and deny accordingly.

        Note:
        - /api/v1/teams/{team_id}/mcp/tool_catalogs (and related MCP catalog endpoints) use get_current_user (JWT-only)
          and perform explicit role checks via list_team_members. These routes do not accept X-API-KEY.
          As a result, X-API-KEY requests return 401/403, while a valid JWT bearer with the required manager role
          (owner/admin/lead) returns 200.
        - Virtual API keys can carry org_id/team_id metadata, but membership/role checks are enforced against the
          authenticated user’s memberships, not the key metadata.
        """
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping team membership access pattern test")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        u = APIClient(base)
        creds = {"username": f"vk_team_nm_{int(time.time())}", "email": f"vk_team_nm_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            u.register(**creds)
        except httpx.HTTPStatusError:
            pass
        u.login(creds["username"], creds["password"])  # bearer for user
        uid = u.get_current_user().get("id")

        # Create org and a team; do NOT add the user to team
        org = api_client.client.post("/api/v1/admin/orgs", json={"name": f"VK Org TNonMem {uuid.uuid4().hex[:6]}"}, headers=headers)
        assert org.status_code == 200, org.text
        org_id = org.json().get("id")
        team = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/teams",
            json={"name": f"VK Team TNonMem {uuid.uuid4().hex[:4]}"},
            headers=headers,
        )
        assert team.status_code == 200, team.text
        team_id = team.json().get("id")

        # Mint a team-scoped key for the user (user is not a team member)
        mk = api_client.client.post(
            f"/api/v1/admin/users/{uid}/virtual-keys",
            json={"name": "vk-team-nonmember", "expires_in_days": 1, "team_id": team_id, "allowed_paths": ["/api/v1/rag"], "allowed_methods": ["POST"]},
            headers=headers,
        )
        assert mk.status_code == 200, mk.text
        key = mk.json().get("key")
        assert key

        # Team-managed endpoint (MCP catalogs) requires JWT + team manager membership; X-API-KEY is unsupported and should 401
        r_xkey = u.client.get(f"/api/v1/teams/{team_id}/mcp/tool_catalogs", headers={"X-API-KEY": key})
        assert r_xkey.status_code in (401, 403)

        # With user's bearer (non-manager, non-member): expect 403
        r_bearer = u.client.get(f"/api/v1/teams/{team_id}/mcp/tool_catalogs")
        assert r_bearer.status_code == 403

        # Now add user to the team as lead and verify access becomes 200
        add_team = api_client.client.post(
            f"/api/v1/admin/teams/{team_id}/members",
            json={"user_id": uid, "role": "lead"},
            headers=headers,
        )
        assert add_team.status_code == 200, add_team.text
        r_bearer2 = u.client.get(f"/api/v1/teams/{team_id}/mcp/tool_catalogs")
        assert r_bearer2.status_code == 200

    def test_27_admin_promote_demote_team_role_toggles_access(self, api_client):
        """Admin removes and re-adds a user's team membership to change role; access toggles accordingly.

        Flow:
        - Add user as 'member' => GET team catalogs forbidden (403)
        - Promote to 'lead' (remove + add with role lead) => GET team catalogs allowed (200)
        - Demote back to 'member' (remove + add as member) => GET team catalogs forbidden (403)
        """
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping promote/demote test")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        u = APIClient(base)
        creds = {"username": f"vk_team_role_{int(time.time())}", "email": f"vk_team_role_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            u.register(**creds)
        except httpx.HTTPStatusError:
            pass
        u.login(creds["username"], creds["password"])  # bearer
        uid = u.get_current_user().get("id")

        # Create org + team
        org = api_client.client.post("/api/v1/admin/orgs", json={"name": f"VK Org Role {uuid.uuid4().hex[:6]}"}, headers=headers)
        assert org.status_code == 200, org.text
        org_id = org.json().get("id")
        team = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/teams",
            json={"name": f"VK Team Role {uuid.uuid4().hex[:4]}"},
            headers=headers,
        )
        assert team.status_code == 200, team.text
        team_id = team.json().get("id")

        # 1) Add as member
        add_member = api_client.client.post(
            f"/api/v1/admin/teams/{team_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=headers,
        )
        assert add_member.status_code == 200, add_member.text
        r1 = u.client.get(f"/api/v1/teams/{team_id}/mcp/tool_catalogs")
        assert r1.status_code == 403

        # 2) Promote to lead
        rem = api_client.client.delete(f"/api/v1/admin/teams/{team_id}/members/{uid}", headers=headers)
        assert rem.status_code in (200, 204)
        add_lead = api_client.client.post(
            f"/api/v1/admin/teams/{team_id}/members",
            json={"user_id": uid, "role": "lead"},
            headers=headers,
        )
        assert add_lead.status_code == 200, add_lead.text
        r2 = u.client.get(f"/api/v1/teams/{team_id}/mcp/tool_catalogs")
        assert r2.status_code == 200

        # 3) Demote back to member
        rem2 = api_client.client.delete(f"/api/v1/admin/teams/{team_id}/members/{uid}", headers=headers)
        assert rem2.status_code in (200, 204)
        add_member2 = api_client.client.post(
            f"/api/v1/admin/teams/{team_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=headers,
        )
        assert add_member2.status_code == 200, add_member2.text
        r3 = u.client.get(f"/api/v1/teams/{team_id}/mcp/tool_catalogs")
        assert r3.status_code == 403

    def test_26_admin_list_api_keys_fields_no_org_team(self, api_client):
        """Explicitly confirm admin list API keys does not expose org_id/team_id; rely on audit log for those."""
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping admin list API keys field test")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        u = APIClient(base)
        creds = {"username": f"vk_list_{int(time.time())}", "email": f"vk_list_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            u.register(**creds)
        except httpx.HTTPStatusError:
            pass
        u.login(creds["username"], creds["password"])  # bearer for /auth/me
        uid = u.get_current_user().get("id")

        # Mint key with org/team
        # Create org and team
        org = api_client.client.post("/api/v1/admin/orgs", json={"name": f"VK Org List {uuid.uuid4().hex[:6]}"}, headers=headers)
        assert org.status_code == 200, org.text
        org_id = org.json().get("id")
        team = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/teams",
            json={"name": f"VK Team List {uuid.uuid4().hex[:4]}"},
            headers=headers,
        )
        assert team.status_code == 200, team.text
        team_id = team.json().get("id")

        mk = api_client.client.post(
            f"/api/v1/admin/users/{uid}/virtual-keys",
            json={"name": "vk-list-metadata", "expires_in_days": 1, "org_id": org_id, "team_id": team_id},
            headers=headers,
        )
        assert mk.status_code == 200, mk.text
        key_id = mk.json().get("id")
        assert key_id

        # Admin list user API keys does not include org_id/team_id in APIKeyMetadata schema
        listing = api_client.client.get(f"/api/v1/admin/users/{uid}/api-keys", headers=headers)
        assert listing.status_code == 200, listing.text
        items = listing.json()
        assert isinstance(items, list) and len(items) >= 1
        # Ensure keys in response do not include org_id/team_id
        sample = items[0]
        assert "org_id" not in sample and "team_id" not in sample

        # Rely on audit log for org/team confirmation
        log = api_client.client.get(f"/api/v1/admin/api-keys/{key_id}/audit-log", headers=headers)
        assert log.status_code == 200
        entries = log.json().get("items", [])
        assert entries
        created = next((e for e in entries if (e.get("action") or "").startswith("created")), entries[0])
        details = created.get("details")
        if isinstance(details, str):
            try:
                import json as _json
                details = _json.loads(details)
            except Exception:
                details = {}
        assert isinstance(details, dict)
        assert details.get("org_id") == org_id
        if team_id is not None:
            assert details.get("team_id") == team_id


class TestOrgsTeamsRBAC:
    """Admin creates org/team and manages memberships; verifies listings reflect assignments."""

    def test_30_org_team_membership_crud(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping org/team tests")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        u1 = APIClient(base)
        u2 = APIClient(base)

        # Create two users and obtain their IDs
        for cli, prefix in ((u1, "orgA"), (u2, "orgB")):
            creds = {"username": f"{prefix}_{int(time.time())}", "email": f"{prefix}_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
            try:
                cli.register(**creds)
            except httpx.HTTPStatusError:
                pass
            cli.login(creds["username"], creds["password"])  # for /auth/me

        uid1 = u1.get_current_user().get("id")
        uid2 = u2.get_current_user().get("id")
        assert isinstance(uid1, int) and isinstance(uid2, int)

        # Create organization
        org = api_client.client.post("/api/v1/admin/orgs", json={"name": f"E2E Org {uuid.uuid4().hex[:6]}"}, headers=headers)
        assert org.status_code == 200, org.text
        org_id = org.json().get("id")
        assert isinstance(org_id, int)

        # Create team under org
        team = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/teams",
            json={"name": f"E2E Team {uuid.uuid4().hex[:4]}"},
            headers=headers,
        )
        assert team.status_code == 200, team.text
        team_id = team.json().get("id")
        assert isinstance(team_id, int)

        # Add members to org and team
        add_org_1 = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/members",
            json={"user_id": uid1, "role": "member"},
            headers=headers,
        )
        assert add_org_1.status_code == 200, add_org_1.text

        add_team_1 = api_client.client.post(
            f"/api/v1/admin/teams/{team_id}/members",
            json={"user_id": uid1, "role": "member"},
            headers=headers,
        )
        assert add_team_1.status_code == 200, add_team_1.text

        add_org_2 = api_client.client.post(
            f"/api/v1/admin/orgs/{org_id}/members",
            json={"user_id": uid2, "role": "member"},
            headers=headers,
        )
        assert add_org_2.status_code == 200, add_org_2.text

        # List team members and verify
        list_team = api_client.client.get(f"/api/v1/admin/teams/{team_id}/members", headers=headers)
        assert list_team.status_code == 200
        members = list_team.json()
        ids = {m.get("user_id") for m in members}
        assert uid1 in ids

        # List org members and verify
        list_org = api_client.client.get(f"/api/v1/admin/orgs/{org_id}/members", headers=headers)
        assert list_org.status_code == 200
        omembers = list_org.json()
        o_ids = {m.get("user_id") for m in omembers}
        assert uid1 in o_ids and uid2 in o_ids

        # Verify user memberships endpoint
        u1_m = api_client.client.get(f"/api/v1/admin/users/{uid1}/org-memberships", headers=headers)
        assert u1_m.status_code == 200
        mems = u1_m.json()
        assert isinstance(mems, list) and any(x.get("org_id") == org_id for x in mems)

        # Remove u1 from team and verify removal
        rem = api_client.client.delete(f"/api/v1/admin/teams/{team_id}/members/{uid1}", headers=headers)
        assert rem.status_code in (200, 204)
        list_team2 = api_client.client.get(f"/api/v1/admin/teams/{team_id}/members", headers=headers)
        ids2 = {m.get("user_id") for m in list_team2.json()}
        assert uid1 not in ids2


class TestAdminRoleAssignment:
    """Admin elevates/demotes a user role and verifies admin route access toggles accordingly."""

    def test_40_admin_elevate_and_demote_role(self, api_client):
        _require_multi_user(api_client)
        admin_token = os.getenv("E2E_ADMIN_BEARER")
        if not admin_token:
            pytest.skip("E2E_ADMIN_BEARER not set; skipping role assignment tests")
        headers = {"Authorization": f"Bearer {admin_token}"}

        base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
        user = APIClient(base)
        creds = {"username": f"role_toggle_{int(time.time())}", "email": f"role_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
        try:
            user.register(**creds)
        except httpx.HTTPStatusError:
            pass
        user.login(creds["username"], creds["password"])  # non-admin bearer
        uid = user.get_current_user().get("id")

        # Non-admin forbidden
        r_forbidden = user.client.get("/api/v1/admin/users")
        assert r_forbidden.status_code == 403

        # Elevate to admin
        elev = api_client.client.put(
            f"/api/v1/admin/users/{uid}",
            json={"role": "admin"},
            headers=headers,
        )
        assert elev.status_code == 200, elev.text

        # Now should access admin endpoint with same bearer
        r_admin = user.client.get("/api/v1/admin/users")
        assert r_admin.status_code == 200

        # Demote back to user
        dem = api_client.client.put(
            f"/api/v1/admin/users/{uid}",
            json={"role": "user"},
            headers=headers,
        )
        assert dem.status_code == 200, dem.text

        # Should be forbidden again
        r_forbidden_again = user.client.get("/api/v1/admin/users")
        assert r_forbidden_again.status_code == 403
