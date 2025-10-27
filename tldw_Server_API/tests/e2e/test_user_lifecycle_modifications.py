"""
test_user_lifecycle_modifications.py
End-to-end tests focused on user lifecycle modifications and index consistency.

Covers:
- Upload + embeddings + search/RAG visibility
- Update content -> re-embed -> search/RAG reflect new content
- Version rollback restores old content and search visibility
- Multi-user data isolation (cannot access or see other users' media)
"""

import os
import time
from typing import Dict, Any, Optional, List

import httpx
import pytest

from fixtures import (
    api_client,
    data_tracker,
    create_test_file,
    cleanup_test_file,
    AssertionHelpers,
    APIClient,
)


class TestUserLifecycleModifications:
    """Lifecycle tests around updates, embeddings, search and rollback."""

    media_id: Optional[int] = None
    token_old = "OMEGA_E2E_TOKEN_12345"
    token_new = "SIGMA_E2E_TOKEN_98765"

    def _poll_embeddings_ready(self, client: APIClient, media_id: int, timeout_s: int = 20) -> bool:
        start = time.time()
        while time.time() - start < timeout_s:
            try:
                r = client.client.get(f"{client.base_url}/api/v1/media/{media_id}/embeddings/status")
                if r.status_code == 200 and r.json().get("has_embeddings"):
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _search_contains_media(self, response: Dict[str, Any], media_id: int) -> bool:
        results = response if isinstance(response, list) else response.get("results") or response.get("items", [])
        ids: List[Optional[int]] = [(x.get("id") or x.get("media_id")) for x in results]
        return media_id in ids

    def test_01_upload_embed_and_search(self, api_client, data_tracker):
        """Upload a doc with a unique token, generate embeddings, verify search/RAG visibility."""
        content_v1 = f"This is lifecycle v1 with token: {self.token_old}. Some extra context for indexing."
        file_path = create_test_file(content_v1)
        data_tracker.add_file(file_path)

        try:
            resp = api_client.upload_media(
                file_path=file_path,
                title="Lifecycle Modification Doc",
                media_type="document",
                generate_embeddings=True,
            )
            media_id = AssertionHelpers.assert_successful_upload(resp)
            data_tracker.add_media(media_id)
            TestUserLifecycleModifications.media_id = media_id

            # Wait for embeddings to be ready (best-effort)
            self._poll_embeddings_ready(api_client, media_id, timeout_s=20)

            # Text search should find the token
            sr = api_client.search_media(self.token_old, limit=10)
            assert self._search_contains_media(sr, media_id), "Uploaded item not found via text search"

            # RAG search may rely on embeddings; allow soft assertion
            try:
                rr = api_client.rag_simple_search(query=self.token_old, databases=["media"], top_k=5)
                if rr.get("success"):
                    results = rr.get("results", [])
                    assert isinstance(results, list)
                    assert any(self.token_old.lower() in (r.get("content", "").lower()) for r in results), \
                        "RAG results do not include expected token"
            except httpx.HTTPStatusError:
                pytest.skip("RAG endpoints unavailable; core upload/search verified")
        finally:
            cleanup_test_file(file_path)

    def test_02_update_content_reembed_and_verify_indexes(self, api_client):
        """Update media content, regenerate embeddings, verify search/RAG reflect new token and not old."""
        if not TestUserLifecycleModifications.media_id:
            pytest.skip("No media from previous step")
        mid = TestUserLifecycleModifications.media_id

        new_content = f"This is lifecycle v2 with token: {self.token_new}. Updated content replacing previous token."

        # Update content (creates new document version and updates FTS)
        r = api_client.client.put(
            f"{api_client.base_url}/api/v1/media/{mid}",
            json={"content": new_content, "title": "Lifecycle Modification Doc (updated)"},
            headers=api_client.get_auth_headers(),
        )
        assert r.status_code == 200, f"Update failed: {r.text}"

        # Ensure embeddings reflect latest content: clear then regenerate
        api_client.client.delete(f"{api_client.base_url}/api/v1/media/{mid}/embeddings")
        gen = api_client.client.post(
            f"{api_client.base_url}/api/v1/media/{mid}/embeddings",
            json={"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "chunk_size": 400},
        )
        assert gen.status_code == 200, f"Embedding regeneration failed: {gen.text}"
        self._poll_embeddings_ready(api_client, mid, timeout_s=20)

        # Text search: old token should no longer match this media; new token should
        sr_old = api_client.search_media(self.token_old, limit=10)
        assert not self._search_contains_media(sr_old, mid), "Old token still found after update"

        sr_new = api_client.search_media(self.token_new, limit=10)
        assert self._search_contains_media(sr_new, mid), "Updated item not found via text search"

        # RAG search on new token should include content; old token should not
        try:
            rr_new = api_client.rag_simple_search(query=self.token_new, databases=["media"], top_k=5)
            if rr_new.get("success"):
                texts = [x.get("content", "").lower() for x in rr_new.get("results", [])]
                assert any(self.token_new.lower() in t for t in texts), "RAG results missing updated token"

            rr_old = api_client.rag_simple_search(query=self.token_old, databases=["media"], top_k=5)
            if rr_old.get("success"):
                texts_old = [x.get("content", "").lower() for x in rr_old.get("results", [])]
                assert all(self.token_old.lower() not in t for t in texts_old), "RAG results still include old token"
        except httpx.HTTPStatusError:
            # If RAG not available, core search assertions are sufficient
            pass

    def test_03_rollback_to_previous_version_and_verify(self, api_client):
        """Rollback to the previous version and verify old token is restored in indexes."""
        if not TestUserLifecycleModifications.media_id:
            pytest.skip("No media from previous step")
        mid = TestUserLifecycleModifications.media_id

        # Get version list to determine prior version number
        lv = api_client.client.get(f"{api_client.base_url}/api/v1/media/{mid}/versions", params={"include_content": False})
        assert lv.status_code == 200, f"List versions failed: {lv.text}"
        versions = lv.json()
        assert isinstance(versions, list) and len(versions) >= 2, "Need at least two versions to rollback"

        latest = versions[0]["version_number"]
        target = versions[1]["version_number"]  # previous version

        rb = api_client.client.post(
            f"{api_client.base_url}/api/v1/media/{mid}/versions/rollback",
            json={"version_number": target},
        )
        assert rb.status_code == 200, f"Rollback failed: {rb.text}"

        # After rollback, FTS should reflect old token; regenerate embeddings to keep RAG in sync
        api_client.client.delete(f"{api_client.base_url}/api/v1/media/{mid}/embeddings")
        api_client.client.post(f"{api_client.base_url}/api/v1/media/{mid}/embeddings", json={})
        self._poll_embeddings_ready(api_client, mid, timeout_s=20)

        sr_old = api_client.search_media(self.token_old, limit=10)
        assert self._search_contains_media(sr_old, mid), "Old token not found after rollback"

        sr_new = api_client.search_media(self.token_new, limit=10)
        assert not self._search_contains_media(sr_new, mid), "New token still found after rollback"


@pytest.mark.multi_user
class TestMultiUserDataIsolation:
    """Multi-user isolation checks: user B cannot see or access user A's media."""

    def test_user_isolation_upload_as_user_a_and_verify_invisible_to_user_b(self, api_client, test_user_credentials, data_tracker):
        # Ensure we're in multi-user mode
        info = api_client.health_check()
        mode_env = os.getenv("AUTH_MODE", "").lower()
        if (info.get("auth_mode") or mode_env) not in {"multi_user", "multi-user", "multiuser"}:
            pytest.skip("Not in multi_user mode")

        # User A: already represented by api_client after login/registration in other tests
        # If not authenticated yet, create/login a user A
        try:
            api_client.register(
                username=test_user_credentials["username"],
                email=test_user_credentials["email"],
                password=test_user_credentials["password"],
            )
        except httpx.HTTPStatusError:
            pass
        try:
            api_client.login(test_user_credentials["username"], test_user_credentials["password"])  # sets headers
        except httpx.HTTPStatusError:
            pass

        # Upload media as user A
        token_a = "USERA_UNIQUE_TOKEN_X"
        path = create_test_file(f"owned by user A: {token_a}")
        data_tracker.add_file(path)
        try:
            resp = api_client.upload_media(file_path=path, title="User A Content", media_type="document", generate_embeddings=False)
            mid_a = AssertionHelpers.assert_successful_upload(resp)
            data_tracker.add_media(mid_a)

            # Sanity: user A can retrieve
            ga = api_client.get_media_item(mid_a)
            assert (ga.get("id") or ga.get("media_id")) == mid_a

            # Create user B and login with separate client
            client_b = APIClient()
            creds_b = {
                "username": f"e2e_user_b_{int(time.time())}",
                "email": f"e2e_user_b_{int(time.time())}@example.com",
                "password": "Password123!",
            }
            try:
                client_b.register(**creds_b)
            except httpx.HTTPStatusError:
                pass
            client_b.login(creds_b["username"], creds_b["password"])  # sets auth headers on client_b

            # User B: cannot fetch user A's media by ID
            r_forbidden = client_b.client.get(f"{client_b.base_url}/api/v1/media/{mid_a}")
            assert r_forbidden.status_code in (403, 404), f"Expected 403/404, got {r_forbidden.status_code}"

            # User B: text search for token_a should NOT return user A item
            sr_b = client_b.client.post(
                f"{client_b.base_url}/api/v1/media/search",
                json={"query": token_a},
                params={"limit": 10},
            )
            if sr_b.status_code == 200:
                res = sr_b.json()
                results = res if isinstance(res, list) else res.get("results") or res.get("items", [])
                ids = [(x.get("id") or x.get("media_id")) for x in results]
                assert mid_a not in ids, "User B search leaked User A's media"

        finally:
            cleanup_test_file(path)
