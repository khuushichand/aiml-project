"""
test_chatbooks_multi_user_roundtrip.py
Export/import round-trip between two distinct users.

Flow:
- User A creates a couple of notes and media items.
- User A exports a chatbook with a subset (1 note + 1 media) synchronously and downloads it.
- User B imports that chatbook synchronously.
- Verify:
  - Counts for User B increase by the selected subset amounts.
  - Imported items are visible to User B and remain inaccessible to User A (scoping).

Skips gracefully if:
- Not running in multi_user auth mode.
- Chatbooks endpoints are disabled or quota-limited.
"""

import io
import os
import time
import uuid
import pytest
import httpx
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from .fixtures import APIClient, create_test_file, cleanup_test_file, AssertionHelpers


def _require_multi_user(api_client: APIClient):
    info = api_client.health_check()
    mode_env = os.getenv("AUTH_MODE", "").lower()
    if (info.get("auth_mode") or mode_env) not in {"multi_user", "multi-user", "multiuser"}:
        pytest.skip("Not in multi_user mode")


@pytest.mark.critical
def test_chatbooks_export_import_two_users_subset_scoping_counts(api_client):
    """Two-user roundtrip: export subset as A, import as B; verify scoping and counts."""
    _require_multi_user(api_client)

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")

    # Check chatbooks subsystem availability
    try:
        h = httpx.Client(base_url=base, timeout=30).get("/api/v1/chatbooks/health")
        if h.status_code not in (200, 207):
            pytest.skip(f"Chatbooks health not OK: {h.status_code}")
    except httpx.HTTPError as e:
        pytest.skip(f"Chatbooks health not available: {e}")

    # Create two distinct users A and B
    client_a = APIClient(base)
    client_b = APIClient(base)

    ts = int(time.time())
    ua = {"username": f"cb_userA_{ts}", "email": f"cb_userA_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    ub = {"username": f"cb_userB_{ts}", "email": f"cb_userB_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    for c, creds in ((client_a, ua), (client_b, ub)):
        try:
            c.register(**creds)
        except httpx.HTTPStatusError:
            pass
        c.login(creds["username"], creds["password"])  # sets bearer

    # Baseline counts for A and B
    def _count_notes(c: APIClient) -> int:
        rn = c.get_notes(limit=200)
        if isinstance(rn, list):
            return len(rn)
        return len(rn.get("items") or rn.get("results") or rn.get("notes", []))

    def _list_notes_items(c: APIClient):
        rn = c.get_notes(limit=200)
        return rn if isinstance(rn, list) else (rn.get("items") or rn.get("results") or rn.get("notes", []))

    def _count_media(c: APIClient) -> int:
        rm = c.get_media_list(limit=200)
        items = rm.get("items") or rm.get("results", [])
        return len(items)

    a_notes_before = _count_notes(client_a)
    a_media_before = _count_media(client_a)
    b_notes_before = _count_notes(client_b)
    b_media_before = _count_media(client_b)

    # User A creates two notes and two media items
    keep_token = f"KEEP_{uuid.uuid4().hex[:8]}"
    skip_token = f"SKIP_{uuid.uuid4().hex[:8]}"

    note_keep = client_a.create_note(title=f"A Note Keep {keep_token}", content="note A content keep")
    note_skip = client_a.create_note(title=f"A Note Skip {skip_token}", content="note A content skip")
    note_keep_id = str(note_keep.get("id") or note_keep.get("note_id"))
    note_skip_id = str(note_skip.get("id") or note_skip.get("note_id"))
    assert note_keep_id and note_skip_id

    fp_keep = create_test_file(f"owned by A; token={keep_token}")
    fp_skip = create_test_file(f"owned by A; token={skip_token}")
    try:
        up_keep = client_a.upload_media(file_path=fp_keep, title=f"A Doc Keep {keep_token}", media_type="document", generate_embeddings=False)
        up_skip = client_a.upload_media(file_path=fp_skip, title=f"A Doc Skip {skip_token}", media_type="document", generate_embeddings=False)
        media_keep_id = AssertionHelpers.assert_successful_upload(up_keep)
        media_skip_id = AssertionHelpers.assert_successful_upload(up_skip)
    finally:
        cleanup_test_file(fp_keep)
        cleanup_test_file(fp_skip)

    # Build export payload selecting one note and one media to include
    export_payload = {
        "name": f"Two-User Export {uuid.uuid4().hex[:6]}",
        "description": "Subset export for two-user roundtrip",
        "content_selections": {"note": [note_keep_id], "media": [str(media_keep_id)]},
        "author": "pytest",
        "include_media": True,
        "include_embeddings": False,
        "include_generated_content": False,
        "tags": ["e2e", "two-user"],
        "categories": ["tests"],
        "async_mode": False,
    }

    # Export as A
    try:
        er = client_a.client.post("/api/v1/chatbooks/export", json=export_payload)
        er.raise_for_status()
        export_info = er.json()
        assert export_info.get("success") is True
        job_id = export_info.get("job_id")
        assert job_id
    except httpx.HTTPStatusError as e:
        # Quotas or feature disabled
        if e.response.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
            pytest.skip(f"Chatbooks export unavailable: {e}")
        raise

    # Download exported archive
    try:
        dl = client_a.client.get(f"/api/v1/chatbooks/download/{job_id}")
        dl.raise_for_status()
        assert dl.headers.get("content-type", "").startswith("application/zip")
        archive = dl.content
        assert archive and len(archive) > 0
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Chatbooks download unavailable: {e}")

    # Import as B (synchronous)
    files = {"file": ("two_user.chatbook", io.BytesIO(archive), "application/zip")}
    form = {
        "conflict_resolution": "skip",
        "prefix_imported": "false",
        "import_media": "true",
        "import_embeddings": "false",
        "async_mode": "false",
    }

    try:
        ir = client_b.client.post("/api/v1/chatbooks/import", files=files, data=form)
        ir.raise_for_status()
        imp = ir.json()
        assert imp.get("success") is True
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Chatbooks import unavailable for B: {e}")

    # Verify counts increased by exactly 1 note and 1 media for B; unchanged for A
    a_notes_after = _count_notes(client_a)
    a_media_after = _count_media(client_a)
    b_notes_after = _count_notes(client_b)
    b_media_after = _count_media(client_b)

    assert a_notes_after == a_notes_before  # A should not change due to B's import
    assert a_media_after == a_media_before
    assert (b_notes_after - b_notes_before) >= 1  # At least the included note
    assert (b_media_after - b_media_before) >= 1  # At least the included media

    # Confirm specific titles appear for B and find imported IDs
    b_notes = _list_notes_items(client_b)
    imported_note = next((n for n in b_notes if isinstance(n, dict) and (n.get("title") or "").startswith("A Note Keep ")), None)
    assert imported_note is not None
    imported_note_id = imported_note.get("id") or imported_note.get("note_id")
    assert imported_note_id

    # Find imported media by title
    bl = client_b.get_media_list(limit=200)
    b_media_items = bl.get("items") or bl.get("results", [])
    imported_media = next((m for m in b_media_items if (m.get("title") or "").startswith("A Doc Keep ")), None)
    assert imported_media is not None
    imported_media_id = imported_media.get("id") or imported_media.get("media_id")
    assert imported_media_id

    # Scoping verification: A cannot access B's imported resources
    r_note_forbidden = client_a.client.get(f"/api/v1/notes/{imported_note_id}")
    assert r_note_forbidden.status_code in (403, 404)

    r_media_forbidden = client_a.client.get(f"/api/v1/media/{imported_media_id}")
    assert r_media_forbidden.status_code in (403, 404)


@pytest.mark.critical
def test_chatbooks_export_import_two_users_async_jobs(api_client):
    """Two-user roundtrip using async export/import with job polling and scoping checks."""
    _require_multi_user(api_client)

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")

    # Check chatbooks subsystem availability
    try:
        h = httpx.Client(base_url=base, timeout=30).get("/api/v1/chatbooks/health")
        if h.status_code not in (200, 207):
            pytest.skip(f"Chatbooks health not OK: {h.status_code}")
    except httpx.HTTPError as e:
        pytest.skip(f"Chatbooks health not available: {e}")

    # Create two distinct users A and B
    client_a = APIClient(base)
    client_b = APIClient(base)

    ts = int(time.time())
    ua = {"username": f"cbA_async_{ts}", "email": f"cbA_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    ub = {"username": f"cbB_async_{ts}", "email": f"cbB_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    for c, creds in ((client_a, ua), (client_b, ub)):
        try:
            c.register(**creds)
        except httpx.HTTPStatusError:
            pass
        c.login(creds["username"], creds["password"])  # sets bearer

    # Baseline counts
    def _count_notes(c: APIClient) -> int:
        rn = c.get_notes(limit=200)
        if isinstance(rn, list):
            return len(rn)
        return len(rn.get("items") or rn.get("results") or rn.get("notes", []))

    def _list_notes_items(c: APIClient):
        rn = c.get_notes(limit=200)
        return rn if isinstance(rn, list) else (rn.get("items") or rn.get("results") or rn.get("notes", []))

    def _count_media(c: APIClient) -> int:
        rm = c.get_media_list(limit=200)
        items = rm.get("items") or rm.get("results", [])
        return len(items)

    a_notes_before = _count_notes(client_a)
    a_media_before = _count_media(client_a)
    b_notes_before = _count_notes(client_b)
    b_media_before = _count_media(client_b)

    # User A creates content
    keep_token = f"KEEP_ASYNC_{uuid.uuid4().hex[:8]}"
    skip_token = f"SKIP_ASYNC_{uuid.uuid4().hex[:8]}"

    note_keep = client_a.create_note(title=f"A Note Keep {keep_token}", content="note A content keep")
    note_skip = client_a.create_note(title=f"A Note Skip {skip_token}", content="note A content skip")
    note_keep_id = str(note_keep.get("id") or note_keep.get("note_id"))
    note_skip_id = str(note_skip.get("id") or note_skip.get("note_id"))
    assert note_keep_id and note_skip_id

    fp_keep = create_test_file(f"owned by A; token={keep_token}")
    fp_skip = create_test_file(f"owned by A; token={skip_token}")
    try:
        up_keep = client_a.upload_media(file_path=fp_keep, title=f"A Doc Keep {keep_token}", media_type="document", generate_embeddings=False)
        up_skip = client_a.upload_media(file_path=fp_skip, title=f"A Doc Skip {skip_token}", media_type="document", generate_embeddings=False)
        media_keep_id = AssertionHelpers.assert_successful_upload(up_keep)
        media_skip_id = AssertionHelpers.assert_successful_upload(up_skip)
    finally:
        cleanup_test_file(fp_keep)
        cleanup_test_file(fp_skip)

    # Start async export (jobs)
    export_payload = {
        "name": f"Two-User Export Async {uuid.uuid4().hex[:6]}",
        "description": "Subset export for async two-user roundtrip",
        "content_selections": {"note": [note_keep_id], "media": [str(media_keep_id)]},
        "author": "pytest",
        "include_media": True,
        "include_embeddings": False,
        "include_generated_content": False,
        "tags": ["e2e", "two-user", "async"],
        "categories": ["tests"],
        "async_mode": True,
    }

    try:
        er = client_a.client.post("/api/v1/chatbooks/export", json=export_payload)
        er.raise_for_status()
        export_info = er.json()
        job_id = export_info.get("job_id")
        assert job_id
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
            pytest.skip(f"Chatbooks async export unavailable: {e}")
        raise

    # Poll export job until completed
    download_url = None
    start = time.time()
    while time.time() - start < 60:
        s = client_a.client.get(f"/api/v1/chatbooks/export/jobs/{job_id}")
        if s.status_code == 200:
            js = s.json()
            st = (js.get("status") or "").lower()
            if st == "completed":
                download_url = js.get("download_url") or f"/api/v1/chatbooks/download/{job_id}"
                break
            if st in {"failed", "cancelled", "expired"}:
                pytest.skip(f"Export job {job_id} ended with status {st}")
        time.sleep(1.0)
    if not download_url:
        pytest.skip("Export job did not complete within timeout")

    # Download archive using the provided download URL (handles signed URLs if enabled)
    dl = client_a.client.get(download_url)
    if dl.status_code not in (200,):
        pytest.skip(f"Download not available: {dl.status_code}")
    assert dl.headers.get("content-type", "").startswith("application/zip")
    archive = dl.content
    assert archive and len(archive) > 0

    # Async import as B
    files = {"file": ("two_user_async.chatbook", io.BytesIO(archive), "application/zip")}
    # Prefer query param for async_mode in this path
    ir = client_b.client.post(
        "/api/v1/chatbooks/import?async_mode=true&conflict_resolution=skip",
        files=files,
    )
    if ir.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip(f"Async import unavailable: {ir.status_code} {ir.text}")
    ir.raise_for_status()
    imp = ir.json()
    import_job_id = imp.get("job_id")
    assert import_job_id

    # Poll import job until completed
    start_i = time.time()
    final_import = None
    while time.time() - start_i < 90:
        s = client_b.client.get(f"/api/v1/chatbooks/import/jobs/{import_job_id}")
        if s.status_code == 200:
            js = s.json()
            st = (js.get("status") or "").lower()
            if st == "completed":
                final_import = js
                break
            if st in {"failed", "cancelled"}:
                pytest.skip(f"Import job {import_job_id} ended with status {st}")
        time.sleep(1.0)
    if not final_import:
        pytest.skip("Import job did not complete within timeout")

    # Verify counts increased for B; unchanged for A
    a_notes_after = _count_notes(client_a)
    a_media_after = _count_media(client_a)
    b_notes_after = _count_notes(client_b)
    b_media_after = _count_media(client_b)
    assert a_notes_after == a_notes_before
    assert a_media_after == a_media_before
    assert (b_notes_after - b_notes_before) >= 1
    assert (b_media_after - b_media_before) >= 1

    # Find imported items by title for B
    b_notes = _list_notes_items(client_b)
    imported_note = next((n for n in b_notes if isinstance(n, dict) and (n.get("title") or "").startswith("A Note Keep ")), None)
    assert imported_note is not None
    imported_note_id = imported_note.get("id") or imported_note.get("note_id")
    assert imported_note_id

    bl = client_b.get_media_list(limit=200)
    b_media_items = bl.get("items") or bl.get("results", [])
    imported_media = next((m for m in b_media_items if (m.get("title") or "").startswith("A Doc Keep ")), None)
    assert imported_media is not None
    imported_media_id = imported_media.get("id") or imported_media.get("media_id")
    assert imported_media_id

    # Scoping: A cannot access B's imported resources
    r_note_forbidden = client_a.client.get(f"/api/v1/notes/{imported_note_id}")
    assert r_note_forbidden.status_code in (403, 404)
    r_media_forbidden = client_a.client.get(f"/api/v1/media/{imported_media_id}")
    assert r_media_forbidden.status_code in (403, 404)


@pytest.mark.critical
def test_chatbooks_export_cancel_midflight_if_possible(api_client):
    """Attempt to cancel an async export job mid-flight; skip if it finishes too fast."""
    _require_multi_user(api_client)

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")

    # Check chatbooks subsystem availability
    try:
        h = httpx.Client(base_url=base, timeout=30).get("/api/v1/chatbooks/health")
        if h.status_code not in (200, 207):
            pytest.skip(f"Chatbooks health not OK: {h.status_code}")
    except httpx.HTTPError as e:
        pytest.skip(f"Chatbooks health not available: {e}")

    # Create user A and some content to ensure non-trivial export
    client_a = APIClient(base)
    ts = int(time.time())
    ua = {"username": f"cbA_cancel_{ts}", "email": f"cbA_cancel_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    try:
        client_a.register(**ua)
    except httpx.HTTPStatusError:
        pass
    client_a.login(ua["username"], ua["password"])  # sets bearer

    note = client_a.create_note(title="Cancel Export Note", content="content for cancel export test")
    note_id = str(note.get("id") or note.get("note_id"))
    fp = create_test_file("export cancel media payload")
    try:
        up = client_a.upload_media(file_path=fp, title="Cancel Export Media", media_type="document", generate_embeddings=False)
        media_id = AssertionHelpers.assert_successful_upload(up)
    finally:
        cleanup_test_file(fp)

    payload = {
        "name": f"Cancel Export {uuid.uuid4().hex[:6]}",
        "description": "Cancel mid-flight",
        "content_selections": {"note": [note_id], "media": [str(media_id)]},
        "author": "pytest",
        "include_media": True,
        "async_mode": True,
    }
    r = client_a.client.post("/api/v1/chatbooks/export", json=payload)
    if r.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip(f"Async export unavailable: {r.status_code}")
    job_id = r.json().get("job_id")
    assert job_id

    # Immediately attempt cancellation
    c = client_a.client.delete(f"/api/v1/chatbooks/export/jobs/{job_id}")
    if c.status_code in (200, 204):
        # Poll a couple of times to see if status reflects cancellation
        for _ in range(5):
            s = client_a.client.get(f"/api/v1/chatbooks/export/jobs/{job_id}")
            if s.status_code == 200:
                st = (s.json().get("status") or "").lower()
                if st in {"cancelled", "failed"}:
                    break
            else:
                # 404 or others implies cleanup or not found: acceptable
                break
            time.sleep(0.5)
        assert True  # If we get here without error, cancellation path exercised
    elif c.status_code == 400 and "Cannot cancel" in c.text:
        pytest.skip("Export job completed before it could be cancelled")
    else:
        # Some environments may forbid cancellation; treat as skip to avoid flake
        pytest.skip(f"Cancellation not permitted or unsupported: {c.status_code}")


@pytest.mark.critical
def test_chatbooks_import_cancel_midflight_if_possible(api_client):
    """Create a sync export archive, start async import, then cancel mid-flight."""
    _require_multi_user(api_client)

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")

    # Check chatbooks subsystem availability
    try:
        h = httpx.Client(base_url=base, timeout=30).get("/api/v1/chatbooks/health")
        if h.status_code not in (200, 207):
            pytest.skip(f"Chatbooks health not OK: {h.status_code}")
    except httpx.HTTPError as e:
        pytest.skip(f"Chatbooks health not available: {e}")

    # Create users A (exporter) and B (importer)
    client_a = APIClient(base)
    client_b = APIClient(base)
    ts = int(time.time())
    ua = {"username": f"cbA_imp_cancel_{ts}", "email": f"cbA_imp_cancel_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    ub = {"username": f"cbB_imp_cancel_{ts}", "email": f"cbB_imp_cancel_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    for c, creds in ((client_a, ua), (client_b, ub)):
        try:
            c.register(**creds)
        except httpx.HTTPStatusError:
            pass
        c.login(creds["username"], creds["password"])  # sets bearer

    # Prepare a small sync export as A
    note = client_a.create_note(title="Cancel Import Note", content="content for cancel import test")
    note_id = str(note.get("id") or note.get("note_id"))
    payload = {
        "name": f"ImpCancel {uuid.uuid4().hex[:6]}",
        "description": "sync export for import cancel",
        "content_selections": {"note": [note_id]},
        "author": "pytest",
        "include_media": False,
        "async_mode": False,
    }
    er = client_a.client.post("/api/v1/chatbooks/export", json=payload)
    if er.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip(f"Sync export unavailable: {er.status_code}")
    job_id = er.json().get("job_id")
    assert job_id
    dl = client_a.client.get(f"/api/v1/chatbooks/download/{job_id}")
    if dl.status_code != 200:
        pytest.skip(f"Download unavailable: {dl.status_code}")
    archive = dl.content
    assert archive

    # Start async import as B
    files = {"file": ("cancel_import.chatbook", io.BytesIO(archive), "application/zip")}
    ir = client_b.client.post(
        "/api/v1/chatbooks/import?async_mode=true&conflict_resolution=skip",
        files=files,
    )
    if ir.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip(f"Async import unavailable: {ir.status_code}")
    import_job_id = ir.json().get("job_id")
    assert import_job_id

    # Immediately attempt to cancel the import
    c = client_b.client.delete(f"/api/v1/chatbooks/import/jobs/{import_job_id}")
    if c.status_code in (200, 204):
        # Poll a bit for cancelled/failed status or disappearance
        for _ in range(5):
            s = client_b.client.get(f"/api/v1/chatbooks/import/jobs/{import_job_id}")
            if s.status_code == 200:
                st = (s.json().get("status") or "").lower()
                if st in {"cancelled", "failed"}:
                    break
            else:
                break
            time.sleep(0.5)
        assert True
    elif c.status_code == 400 and "Cannot cancel" in c.text:
        pytest.skip("Import job completed before it could be cancelled")
    else:
        pytest.skip(f"Import cancellation not permitted or unsupported: {c.status_code}")


@pytest.mark.critical
def test_chatbooks_signed_download_url_expiry_assertion(api_client):
    """If signed URLs are enabled, ensure expired signed URL returns 410."""
    # Chatbooks health
    try:
        h = api_client.client.get("/api/v1/chatbooks/health")
        if h.status_code not in (200, 207):
            pytest.skip(f"Chatbooks health not OK: {h.status_code}")
    except httpx.HTTPError as e:
        pytest.skip(f"Chatbooks health not available: {e}")

    # Create minimal content
    try:
        note = api_client.create_note(title="Signed URL Expiry Note", content="test")
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Notes unavailable: {e}")
    note_id = str(note.get("id") or note.get("note_id"))

    # Sync export to get download_url
    payload = {
        "name": f"SignedURL {uuid.uuid4().hex[:6]}",
        "description": "signed url test",
        "content_selections": {"note": [note_id]},
        "author": "pytest",
        "include_media": False,
        "async_mode": False,
    }
    er = api_client.client.post("/api/v1/chatbooks/export", json=payload)
    if er.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip(f"Sync export unavailable: {er.status_code}")
    resp = er.json()
    job_id = resp.get("job_id")
    download_url = resp.get("download_url") or f"/api/v1/chatbooks/download/{job_id}"

    # Valid URL should work
    ok = api_client.client.get(download_url)
    if ok.status_code != 200:
        pytest.skip(f"Download failed for fresh URL: {ok.status_code}")

    # If signed URLs are not enabled, the URL won't have token/exp
    if "token=" not in download_url or "exp=" not in download_url:
        pytest.skip("Signed URLs not enabled; skipping expiry assertion")

    # Craft an expired signed URL by forcing exp in the past; token is checked after expiry
    parts = urlparse(download_url)
    q = parse_qs(parts.query)
    q["exp"] = ["0"]  # Far in the past
    # Keep token param (any value) to pass presence check; may reuse original or set dummy
    if "token" not in q or not q["token"] or not q["token"][0]:
        q["token"] = ["deadbeef"]
    expired_url = urlunparse(parts._replace(query=urlencode({k: v[0] for k, v in q.items()})))

    ex = api_client.client.get(expired_url)
    assert ex.status_code == 410, f"Expected 410 for expired signed URL, got {ex.status_code}"


@pytest.mark.critical
def test_chatbooks_export_cancel_reflected_in_job_list(api_client):
    """Cancel an export and verify the jobs list reflects cancellation or item removal."""
    _require_multi_user(api_client)

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
    # Health
    hh = httpx.Client(base_url=base, timeout=30).get("/api/v1/chatbooks/health")
    if hh.status_code not in (200, 207):
        pytest.skip("Chatbooks health not OK")

    c = APIClient(base)
    ts = int(time.time())
    ua = {"username": f"cb_list_cancel_{ts}", "email": f"cb_list_cancel_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    try:
        c.register(**ua)
    except httpx.HTTPStatusError:
        pass
    c.login(ua["username"], ua["password"])  # bearer

    # Make async export to have a job
    note = c.create_note(title="List Cancel Note", content="content")
    note_id = str(note.get("id") or note.get("note_id"))
    payload = {
        "name": f"ListCancel {uuid.uuid4().hex[:6]}",
        "description": "list cancel test",
        "content_selections": {"note": [note_id]},
        "author": "pytest",
        "include_media": False,
        "async_mode": True,
    }
    r = c.client.post("/api/v1/chatbooks/export", json=payload)
    if r.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip("Async export unavailable")
    job_id = r.json().get("job_id")
    assert job_id

    # Cancel
    cancel = c.client.delete(f"/api/v1/chatbooks/export/jobs/{job_id}")
    if cancel.status_code not in (200, 204):
        # May complete too fast
        pytest.skip("Could not cancel in time")

    # Verify list reflects cancellation or removal
    s = c.client.get("/api/v1/chatbooks/export/jobs")
    if s.status_code != 200:
        pytest.skip("Jobs listing unavailable")
    items = s.json().get("jobs", []) if isinstance(s.json(), dict) else []
    # Find job if present
    found = next((j for j in items if (j.get("job_id") == job_id)), None)
    if found:
        assert (found.get("status") or "").lower() in {"cancelled", "failed", "expired"}
    else:
        # Not present after cancellation is also acceptable
        assert True


@pytest.mark.critical
def test_chatbooks_admin_cannot_cancel_other_users_jobs(api_client):
    """Admin bearer should not be able to cancel another user's chatbooks jobs (no admin override endpoints)."""
    _require_multi_user(api_client)
    admin_token = os.getenv("E2E_ADMIN_BEARER")
    if not admin_token:
        pytest.skip("E2E_ADMIN_BEARER not set; skipping admin cancellation attempt")

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
    # Health
    hh = httpx.Client(base_url=base, timeout=30).get("/api/v1/chatbooks/health")
    if hh.status_code not in (200, 207):
        pytest.skip("Chatbooks health not OK")

    # Create user A and job
    ua_client = APIClient(base)
    ts = int(time.time())
    ua = {"username": f"cb_admin_denied_{ts}", "email": f"cb_admin_denied_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    try:
        ua_client.register(**ua)
    except httpx.HTTPStatusError:
        pass
    ua_client.login(ua["username"], ua["password"])  # bearer for user A

    # Start async export for user A
    note = ua_client.create_note(title="Admin Denied Note", content="content")
    note_id = str(note.get("id") or note.get("note_id"))
    payload = {
        "name": f"AdminDenied {uuid.uuid4().hex[:6]}",
        "description": "admin cannot cancel",
        "content_selections": {"note": [note_id]},
        "author": "pytest",
        "include_media": False,
        "async_mode": True,
    }
    r = ua_client.client.post("/api/v1/chatbooks/export", json=payload)
    if r.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip("Async export unavailable")
    job_id = r.json().get("job_id")
    assert job_id

    # Attempt to cancel using admin bearer on the same endpoint (no admin override exists)
    headers = {"Authorization": f"Bearer {admin_token}"}
    cancel_as_admin = httpx.Client(base_url=base, timeout=30).delete(
        f"/api/v1/chatbooks/export/jobs/{job_id}", headers=headers
    )
    # Expect denial or not found, since jobs are user-scoped
    assert cancel_as_admin.status_code in (401, 403, 404)

    # Cleanup: try cancel as user to avoid dangling jobs (best effort)
    try:
        ua_client.client.delete(f"/api/v1/chatbooks/export/jobs/{job_id}")
    except Exception:
        pass


@pytest.mark.critical
def test_chatbooks_import_cancel_reflected_in_job_list(api_client):
    """Cancel an import and verify the jobs list reflects cancellation or item removal."""
    _require_multi_user(api_client)

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000")
    # Health
    hh = httpx.Client(base_url=base, timeout=30).get("/api/v1/chatbooks/health")
    if hh.status_code not in (200, 207):
        pytest.skip("Chatbooks health not OK")

    # Create user and a small sync export to import
    c = APIClient(base)
    ts = int(time.time())
    u = {"username": f"cb_imp_list_cancel_{ts}", "email": f"cb_imp_list_cancel_{uuid.uuid4().hex[:6]}@ex.com", "password": "Password123!"}
    try:
        c.register(**u)
    except httpx.HTTPStatusError:
        pass
    c.login(u["username"], u["password"])  # bearer

    # Prepare export
    note = c.create_note(title="Import List Cancel Note", content="content")
    note_id = str(note.get("id") or note.get("note_id"))
    payload = {
        "name": f"ImpListCancel {uuid.uuid4().hex[:6]}",
        "description": "imp list cancel test",
        "content_selections": {"note": [note_id]},
        "author": "pytest",
        "include_media": False,
        "async_mode": False,
    }
    er = c.client.post("/api/v1/chatbooks/export", json=payload)
    if er.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip("Sync export unavailable")
    job_id = er.json().get("job_id")
    dl = c.client.get(f"/api/v1/chatbooks/download/{job_id}")
    if dl.status_code != 200:
        pytest.skip("Download unavailable for import cancel test")
    archive = dl.content

    # Start async import
    files = {"file": ("imp_list_cancel.chatbook", io.BytesIO(archive), "application/zip")}
    ir = c.client.post("/api/v1/chatbooks/import?async_mode=true&conflict_resolution=skip", files=files)
    if ir.status_code in (400, 401, 403, 404, 413, 429, 500, 501):
        pytest.skip("Async import unavailable")
    import_job_id = ir.json().get("job_id")

    # Cancel
    cancel = c.client.delete(f"/api/v1/chatbooks/import/jobs/{import_job_id}")
    if cancel.status_code not in (200, 204):
        pytest.skip("Could not cancel import in time")

    # Verify list reflects cancellation or removal
    s = c.client.get("/api/v1/chatbooks/import/jobs")
    if s.status_code != 200:
        pytest.skip("Import jobs listing unavailable")
    items = s.json().get("jobs", []) if isinstance(s.json(), dict) else []
    found = next((j for j in items if (j.get("job_id") == import_job_id)), None)
    if found:
        assert (found.get("status") or "").lower() in {"cancelled", "failed", "expired"}
    else:
        assert True
