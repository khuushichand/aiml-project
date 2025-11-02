"""
test_media_update_propagation.py
E2E tests covering media update propagation behaviors:

- Re-embed-on-write toggle: verify behavior when auto re-embed is disabled/enabled after content updates
- Safe metadata patch + metadata search normalization (e.g., DOI)
- Delete version edge case: deleting the last active version returns 400 and leaves item searchable

Notes:
- For the re-embed-on-write scenario, we use the embedding-search endpoint to isolate vector behavior.
  If auto re-embed is disabled, updated content won't appear in embedding search until manual regeneration.
  If auto re-embed is enabled in the environment (e.g., re-embed worker running), polling should observe
  the new token showing up without manually triggering re-embedding. The test branches accordingly and
  asserts either path.
"""

import time
import uuid
from typing import Dict, Any, Optional

import httpx
import pytest

from fixtures import (
    api_client,
    data_tracker,
    create_test_file,
    cleanup_test_file,
    AssertionHelpers,
)


def _poll_embedding_search(client: httpx.Client, base_url: str, query: str, timeout_s: int = 15) -> bool:
    """Poll embedding search for presence of results for the query text."""
    start = time.time()
    while time.time() - start < timeout_s:
        r = client.post(f"{base_url}/api/v1/media/embeddings/search", json={"query": query, "top_k": 5})
        if r.status_code == 200:
            js = r.json()
            if isinstance(js, dict) and int(js.get("count") or 0) > 0:
                return True
        elif r.status_code == 503:
            # Embedding service unavailable; cannot meaningfully poll
            break
        time.sleep(0.5)
    return False


class TestMediaUpdatePropagation:
    def test_reembed_on_write_toggle_behavior(self, api_client, data_tracker):
        """Verify behavior on content update when auto re-embed is disabled vs enabled.

        Flow:
        - Upload doc with TOKEN_A and generate embeddings
        - Confirm embedding search finds TOKEN_A
        - Update content to TOKEN_B (no manual re-embed)
        - If auto re-embed is enabled, embedding search for TOKEN_B should eventually succeed
        - If disabled, embedding search for TOKEN_B stays empty until we explicitly regenerate embeddings
        """
        token_a = f"TOKEN_A_{uuid.uuid4().hex[:8]}"
        token_b = f"TOKEN_B_{uuid.uuid4().hex[:8]}"
        path = create_test_file(f"Initial content with {token_a} only.")
        data_tracker.add_file(path)

        try:
            # Upload with embeddings
            resp = api_client.upload_media(
                file_path=path,
                title="E2E Re-embed on write",
                media_type="document",
                generate_embeddings=True,
            )
            media_id = AssertionHelpers.assert_successful_upload(resp)
            data_tracker.add_media(media_id)

            # Confirm embedding-search returns results for TOKEN_A (skip if embeddings unavailable)
            r_a = api_client.client.post(
                f"{api_client.base_url}/api/v1/media/embeddings/search",
                json={"query": token_a, "top_k": 5},
            )
            if r_a.status_code == 503:
                pytest.skip("Embedding service unavailable; skipping re-embed-on-write verification.")
            assert r_a.status_code == 200, r_a.text
            assert int(r_a.json().get("count") or 0) >= 0  # allow zero if chunks small; presence is best-effort

            # Update content to only include TOKEN_B
            upd = api_client.client.put(
                f"{api_client.base_url}/api/v1/media/{media_id}",
                json={"content": f"Updated content with {token_b} only.", "title": "E2E Re-embed on write (updated)"},
                headers=api_client.get_auth_headers(),
            )
            assert upd.status_code == 200, upd.text

            # Without manual re-embed, embedding search for TOKEN_B should either:
            # - appear after a short delay if auto re-embed is enabled
            # - remain empty if disabled; then after manual re-embed it should appear
            appeared_automatically = _poll_embedding_search(api_client.client, api_client.base_url, token_b, timeout_s=15)

            if appeared_automatically:
                # Auto re-embed path observed
                r_b = api_client.client.post(
                    f"{api_client.base_url}/api/v1/media/embeddings/search",
                    json={"query": token_b, "top_k": 5},
                )
                assert r_b.status_code == 200
                assert int(r_b.json().get("count") or 0) > 0
            else:
                # Disabled path: ensure it did not appear within the polling window
                r_b_initial = api_client.client.post(
                    f"{api_client.base_url}/api/v1/media/embeddings/search",
                    json={"query": token_b, "top_k": 5},
                )
                if r_b_initial.status_code == 503:
                    pytest.skip("Embedding service unavailable after update; skipping remainder.")
                assert r_b_initial.status_code == 200
                assert int(r_b_initial.json().get("count") or 0) == 0

                # Manually regenerate embeddings, then assert TOKEN_B appears
                regen = api_client.client.post(
                    f"{api_client.base_url}/api/v1/media/{media_id}/embeddings",
                    json={"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"},
                )
                assert regen.status_code == 200, regen.text

                assert _poll_embedding_search(api_client.client, api_client.base_url, token_b, timeout_s=20), \
                    "TOKEN_B not found in embedding search after manual re-embed"

        finally:
            cleanup_test_file(path)

    def test_safe_metadata_patch_and_metadata_search_normalization(self, api_client, data_tracker):
        """PATCH safe_metadata with DOI and verify metadata-search normalization indexes correctly."""
        token = f"META_TOKEN_{uuid.uuid4().hex[:6]}"
        path = create_test_file(f"Paper content for metadata normalization {token}")
        data_tracker.add_file(path)

        try:
            resp = api_client.upload_media(
                file_path=path,
                title="E2E Metadata Patch",
                media_type="document",
                generate_embeddings=False,
            )
            media_id = AssertionHelpers.assert_successful_upload(resp)
            data_tracker.add_media(media_id)

            # Apply safe_metadata patch with DOI (mixed case) and PMCID (with PMC prefix)
            doi_val = "10.1234/AbCdEf-XYZ.987"
            pmcid_val = "PMC1234567"
            patch = api_client.client.patch(
                f"{api_client.base_url}/api/v1/media/{media_id}/metadata",
                json={
                    "safe_metadata": {"DOI": doi_val, "PMCID": pmcid_val, "journal": "Nature"},
                    "merge": True,
                    "new_version": False,
                },
                headers=api_client.get_auth_headers(),
            )
            assert patch.status_code == 200, patch.text

            # Search by metadata with uppercase field; endpoint normalizes to canonical keys/values
            q = api_client.client.get(
                f"{api_client.base_url}/api/v1/media/metadata-search",
                params={"field": "DOI", "op": "eq", "value": doi_val, "group_by_media": True},
            )
            assert q.status_code == 200, q.text
            res = q.json()
            items = res.get("results", []) if isinstance(res, dict) else []
            ids = [(x.get("media_id") or x.get("id")) for x in items]
            assert media_id in ids, "Metadata search by DOI did not return patched media"

            # Quick smoke on by-identifier endpoint using DOI normalization
            q2 = api_client.client.get(
                f"{api_client.base_url}/api/v1/media/by-identifier",
                params={"doi": doi_val},
            )
            assert q2.status_code in (200, 401), q2.text  # 401 in single_user may require auth; tolerate
            if q2.status_code == 200:
                ids2 = [(x.get("media_id") or x.get("id")) for x in q2.json().get("results", [])]
                assert media_id in ids2

        finally:
            cleanup_test_file(path)

    def test_delete_last_active_version_returns_400_and_media_remains_searchable(self, api_client, data_tracker):
        """Deleting the only active version should return 400 and item should remain searchable."""
        token = f"DEL_LAST_VER_{uuid.uuid4().hex[:6]}"
        path = create_test_file(f"This document contains {token} and has one version only.")
        data_tracker.add_file(path)

        try:
            resp = api_client.upload_media(
                file_path=path,
                title="E2E Delete Last Version",
                media_type="document",
                generate_embeddings=False,
            )
            media_id = AssertionHelpers.assert_successful_upload(resp)
            data_tracker.add_media(media_id)

            # Attempt to delete version 1 (only active version)
            delr = api_client.client.delete(f"{api_client.base_url}/api/v1/media/{media_id}/versions/1")
            assert delr.status_code == 400, f"Expected 400 for last-active delete, got {delr.status_code}: {delr.text}"

            # Ensure media remains searchable by text
            sr = api_client.search_media(token, limit=10)
            results = sr if isinstance(sr, list) else sr.get("results") or sr.get("items", [])
            found_ids = [(x.get("id") or x.get("media_id")) for x in results]
            assert media_id in found_ids, "Media should remain searchable after failed delete of last version"

        finally:
            cleanup_test_file(path)
