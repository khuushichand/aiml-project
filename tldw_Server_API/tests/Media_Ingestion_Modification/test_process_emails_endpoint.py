from io import BytesIO
import zipfile
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client():
    return TestClient(app)


def test_process_emails_endpoint_basic():
    # Build a minimal EML file
    content = (
        b"From: Alice <alice@example.com>\r\n"
        b"To: Bob <bob@example.com>\r\n"
        b"Subject: Test Email\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Hello Bob, this is a test.\r\n"
    )

    files = {
        "files": ("test.eml", BytesIO(content), "message/rfc822"),
    }

    with _client() as c:
        r = c.post("/api/v1/media/process-emails", files=files)
        assert r.status_code in (200, 207)
        data = r.json()
        assert isinstance(data.get("results"), list)
        assert len(data["results"]) >= 1
        first = data["results"][0]
        assert first.get("media_type") == "email"
        md = first.get("metadata", {})
        assert md.get("email", {}).get("subject") == "Test Email"


def _build_zip_of_emls() -> bytes:
    # Build two simple EMLs in a zip archive (in-memory)
    eml1 = (
        b"From: A <a@example.com>\r\n"
        b"To: B <b@example.com>\r\n"
        b"Subject: Zip One\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Body one.\r\n"
    )
    eml2 = (
        b"From: C <c@example.com>\r\n"
        b"To: D <d@example.com>\r\n"
        b"Subject: Zip Two\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Body two.\r\n"
    )
    bio = BytesIO()
    with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('one.eml', eml1)
        zf.writestr('two.eml', eml2)
    bio.seek(0)
    return bio.getvalue()


def test_process_emails_endpoint_zip_archive():
    zip_bytes = _build_zip_of_emls()
    files = {
        "files": ("emails.zip", BytesIO(zip_bytes), "application/zip"),
    }
    with _client() as c:
        r = c.post(
            "/api/v1/media/process-emails",
            files=files,
            data={
                "accept_archives": "true",
                "perform_chunking": "true",
            },
        )
        assert r.status_code in (200, 207)
        data = r.json()
        res = data.get("results")
        assert isinstance(res, list) and len(res) >= 2
        subjects = sorted([item.get("metadata", {}).get("email", {}).get("subject") for item in res if isinstance(item, dict)])
        assert subjects[0] == "Zip One" and subjects[1] == "Zip Two"
        # Assert archive grouping keyword is present on each child
        for item in res:
            if isinstance(item, dict):
                kws = item.get("keywords") or []
                assert "email_archive:emails" in kws, f"Archive keyword missing in child: {kws}"


def _build_mbox_two_emails() -> bytes:
    # Build a small mbox file with two minimal emails via mailbox
    import mailbox as _mailbox
    import tempfile as _tempfile
    from email.message import EmailMessage

    with _tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
    try:
        mbox = _mailbox.mbox(tmp_path)
        # Email 1
        msg1 = EmailMessage()
        msg1["From"] = "A <a@example.com>"
        msg1["To"] = "B <b@example.com>"
        msg1["Subject"] = "Mbox One"
        msg1.set_content("Hello from mbox one.")
        mbox.add(msg1)
        # Email 2
        msg2 = EmailMessage()
        msg2["From"] = "C <c@example.com>"
        msg2["To"] = "D <d@example.com>"
        msg2["Subject"] = "Mbox Two"
        msg2.set_content("Hello from mbox two.")
        mbox.add(msg2)
        mbox.flush()
        mbox.close()
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass


def test_process_emails_endpoint_mbox_archive():
    mbox_bytes = _build_mbox_two_emails()
    files = {
        "files": ("emails.mbox", BytesIO(mbox_bytes), "application/mbox"),
    }
    with _client() as c:
        r = c.post(
            "/api/v1/media/process-emails",
            files=files,
            data={
                "accept_mbox": "true",
                "perform_chunking": "true",
            },
        )
        assert r.status_code in (200, 207)
        data = r.json()
        res = data.get("results")
        assert isinstance(res, list) and len(res) >= 2
        subjects = sorted([item.get("metadata", {}).get("email", {}).get("subject") for item in res if isinstance(item, dict)])
        assert subjects[0] == "Mbox One" and subjects[1] == "Mbox Two"
        # Assert mbox grouping keyword is present on each child
        for item in res:
            if isinstance(item, dict):
                kws = item.get("keywords") or []
                assert "email_mbox:emails" in kws, f"MBOX keyword missing in child: {kws}"


def test_process_emails_endpoint_mbox_guardrail_too_many_messages():
    # Lower guardrail for internal files to a small number, then exceed it
    import mailbox as _mailbox
    import tempfile as _tempfile
    from email.message import EmailMessage
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Email import Email_Processing_Lib as email_lib

    # Monkeypatch guardrail limits to keep the test lightweight
    archive_cfg = email_lib.DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {})
    orig_max_files = archive_cfg.get('max_internal_files', 100)
    try:
        archive_cfg['max_internal_files'] = 5

        with _tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            mbox = _mailbox.mbox(tmp_path)
            # Create 6 messages to exceed the limit of 5
            for i in range(6):
                msg = EmailMessage()
                msg["From"] = f"X <x{i}@example.com>"
                msg["To"] = "Y <y@example.com>"
                msg["Subject"] = f"Msg {i}"
                msg.set_content("Hi")
                mbox.add(msg)
            mbox.flush()
            mbox.close()
            with open(tmp_path, "rb") as f:
                mbox_bytes = f.read()
        finally:
            import os as _os
            try:
                _os.unlink(tmp_path)
            except Exception:
                pass

        files = {
            "files": ("emails.mbox", BytesIO(mbox_bytes), "application/mbox"),
        }
        with _client() as c:
            r = c.post(
                "/api/v1/media/process-emails",
                files=files,
                data={
                    "accept_mbox": "true",
                    "perform_chunking": "false",
                },
            )
            assert r.status_code in (200, 207)
            data = r.json()
            res = data.get("results") or []
            # Expect at least one Error item indicating too many messages
            errors = [it for it in res if isinstance(it, dict) and it.get("status") == "Error" and "too many messages" in str(it.get("error", "")).lower()]
            assert errors, f"Expected guardrail error for too many messages, got: {res}"
    finally:
        archive_cfg['max_internal_files'] = orig_max_files


def test_process_emails_endpoint_mbox_guardrail_oversized_bytes():
    # Lower size guardrail to 1 MB and build a ~1.5 MB mbox to trigger size error
    import mailbox as _mailbox
    import tempfile as _tempfile
    from email.message import EmailMessage
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Email import Email_Processing_Lib as email_lib

    archive_cfg = email_lib.DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {})
    orig_max_size_mb = archive_cfg.get('max_internal_uncompressed_size_mb', 200)
    try:
        archive_cfg['max_internal_uncompressed_size_mb'] = 1  # 1 MB

        # Build one big message so the resulting mbox exceeds 1 MB
        big_payload = ("X" * (1024 * 1024 + 500 * 1024))  # ~1.5 MB text
        with _tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            mbox = _mailbox.mbox(tmp_path)
            msg = EmailMessage()
            msg["From"] = "Big <big@example.com>"
            msg["To"] = "Dest <dest@example.com>"
            msg["Subject"] = "BigMsg"
            msg.set_content(big_payload)
            mbox.add(msg)
            mbox.flush()
            mbox.close()
            with open(tmp_path, "rb") as f:
                mbox_bytes = f.read()
        finally:
            import os as _os
            try:
                _os.unlink(tmp_path)
            except Exception:
                pass

        files = {
            "files": ("emails.mbox", BytesIO(mbox_bytes), "application/mbox"),
        }
        with _client() as c:
            r = c.post(
                "/api/v1/media/process-emails",
                files=files,
                data={
                    "accept_mbox": "true",
                    "perform_chunking": "false",
                },
            )
            assert r.status_code in (200, 207)
            data = r.json()
            res = data.get("results") or []
            # Expect a single error result for size guardrail
            assert len(res) >= 1 and isinstance(res[0], dict)
            err = res[0]
            assert err.get("status") == "Error"
            assert "exceeds limit" in str(err.get("error", "")).lower()
    finally:
        archive_cfg['max_internal_uncompressed_size_mb'] = orig_max_size_mb


def _build_zip_with_emls(n: int, payload_size: int = 32) -> bytes:
    # Build a zip with n EML files, each with payload_size bytes body
    bio = BytesIO()
    with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(n):
            body = ("X" * payload_size).encode("utf-8")
            eml = (
                b"From: A <a@example.com>\r\n"
                b"To: B <b@example.com>\r\n"
                + f"Subject: Z{i}\r\n".encode("utf-8")
                + b"MIME-Version: 1.0\r\n"
                + b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
                + body
            )
            zf.writestr(f"m{i}.eml", eml)
    bio.seek(0)
    return bio.getvalue()


def test_process_emails_endpoint_zip_guardrail_too_many_files():
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Email import Email_Processing_Lib as email_lib
    archive_cfg = email_lib.DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {})
    orig_max_files = archive_cfg.get('max_internal_files', 100)
    try:
        archive_cfg['max_internal_files'] = 1
        zip_bytes = _build_zip_with_emls(2, payload_size=64)
        files = {
            "files": ("emails.zip", BytesIO(zip_bytes), "application/zip"),
        }
        with _client() as c:
            r = c.post(
                "/api/v1/media/process-emails",
                files=files,
                data={
                    "accept_archives": "true",
                },
            )
            assert r.status_code in (200, 207)
            data = r.json()
            res = data.get("results") or []
            assert len(res) >= 1 and isinstance(res[0], dict)
            err = res[0]
            assert err.get("status") == "Error"
            assert "too many files" in str(err.get("error", "")).lower()
    finally:
        archive_cfg['max_internal_files'] = orig_max_files


def test_process_emails_endpoint_zip_guardrail_oversize():
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Email import Email_Processing_Lib as email_lib
    archive_cfg = email_lib.DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {})
    orig_max_size_mb = archive_cfg.get('max_internal_uncompressed_size_mb', 200)
    try:
        archive_cfg['max_internal_uncompressed_size_mb'] = 1
        # Build one large eml (~1.5MB body)
        big_body_len = 1024 * 1024 + 500 * 1024
        zip_bytes = _build_zip_with_emls(1, payload_size=big_body_len)
        files = {
            "files": ("emails.zip", BytesIO(zip_bytes), "application/zip"),
        }
        with _client() as c:
            r = c.post(
                "/api/v1/media/process-emails",
                files=files,
                data={
                    "accept_archives": "true",
                },
            )
            assert r.status_code in (200, 207)
            data = r.json()
            res = data.get("results") or []
            assert len(res) >= 1 and isinstance(res[0], dict)
            err = res[0]
            assert err.get("status") == "Error"
            assert "exceeds limit" in str(err.get("error", "")).lower()
    finally:
        archive_cfg['max_internal_uncompressed_size_mb'] = orig_max_size_mb


@pytest.mark.performance
def test_process_emails_endpoint_zip_large_container():
    # Build 120 small EMLs and ensure the endpoint expands and processes them
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Email import Email_Processing_Lib as email_lib
    archive_cfg = email_lib.DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {})
    orig_max_files = archive_cfg.get('max_internal_files', 100)
    try:
        archive_cfg['max_internal_files'] = 200
        zip_bytes = _build_zip_with_emls(120, payload_size=64)
        files = {
            "files": ("emails.zip", BytesIO(zip_bytes), "application/zip"),
        }
        with _client() as c:
            r = c.post(
                "/api/v1/media/process-emails",
                files=files,
                data={
                    "accept_archives": "true",
                    "perform_chunking": "false",
                },
            )
            assert r.status_code in (200, 207)
            data = r.json()
            res = data.get("results") or []
            # Expect at least 120 children
            assert isinstance(res, list) and len(res) >= 120
    finally:
        archive_cfg['max_internal_files'] = orig_max_files


@pytest.mark.performance
def test_process_emails_endpoint_mbox_large_container():
    # Build an mbox with 120 small messages; ensure expansion handles volume
    import mailbox as _mailbox
    import tempfile as _tempfile
    from email.message import EmailMessage
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Email import Email_Processing_Lib as email_lib

    archive_cfg = email_lib.DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {})
    orig_max_files = archive_cfg.get('max_internal_files', 100)
    try:
        archive_cfg['max_internal_files'] = 200
        with _tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            mbox = _mailbox.mbox(tmp_path)
            for i in range(120):
                msg = EmailMessage()
                msg["From"] = f"X <x{i}@example.com>"
                msg["To"] = "Y <y@example.com>"
                msg["Subject"] = f"Msg {i}"
                msg.set_content("Hi")
                mbox.add(msg)
            mbox.flush()
            mbox.close()
            with open(tmp_path, "rb") as f:
                mbox_bytes = f.read()
        finally:
            import os as _os
            try:
                _os.unlink(tmp_path)
            except Exception:
                pass

        files = {
            "files": ("emails.mbox", BytesIO(mbox_bytes), "application/mbox"),
        }
        with _client() as c:
            r = c.post(
                "/api/v1/media/process-emails",
                files=files,
                data={
                    "accept_mbox": "true",
                    "perform_chunking": "false",
                },
            )
            assert r.status_code in (200, 207)
            data = r.json()
            res = data.get("results") or []
            assert isinstance(res, list) and len(res) >= 120
    finally:
        archive_cfg['max_internal_files'] = orig_max_files


@pytest.mark.requires_pypff
@pytest.mark.skipif(__import__('importlib').util.find_spec('pypff') is None, reason="pypff is not installed")
def test_process_emails_endpoint_pst_with_pypff_extraction():
    # This test only runs when pypff is installed on the system.
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Email import Email_Processing_Lib as email_lib
    # Use a tiny fake byte buffer; handler will try to open and likely error as invalid PST.
    # The assertion is focused on exercising the pypff code path under real install conditions.
    pst_bytes = b"!pst"
    results = email_lib.process_pst_bytes(
        file_bytes=pst_bytes, pst_name="emails.pst", perform_chunking=False
    )
    assert isinstance(results, list) and len(results) >= 1
    # Either we parse some messages or return an 'Invalid PST/OST file' error, but not the feature-flag message.
    first = results[0]
    assert 'support not enabled' not in str(first.get('error','')).lower()


@pytest.mark.requires_pypff
@pytest.mark.skipif(__import__('os').environ.get('PST_FIXTURE_PATH') in (None, ''), reason="No PST_FIXTURE_PATH provided")
@pytest.mark.skipif(__import__('importlib').util.find_spec('pypff') is None, reason="pypff is not installed")
def test_process_emails_endpoint_pst_recipients_and_date_strict():
    # Requires a tiny valid PST fixture at PST_FIXTURE_PATH with at least one message
    import os
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Email import Email_Processing_Lib as email_lib
    pst_path = os.environ.get('PST_FIXTURE_PATH')
    assert os.path.isfile(pst_path), f"Fixture not found: {pst_path}"
    with open(pst_path, 'rb') as f:
        pst_bytes = f.read()
    results = email_lib.process_pst_bytes(file_bytes=pst_bytes, pst_name="fixture.pst", perform_chunking=False)
    assert isinstance(results, list) and len(results) >= 1
    item = results[0]
    md = item.get('metadata') or {}
    emd = md.get('email') or {}
    # Ensure recipients and date appear (format-agnostic checks)
    assert (emd.get('to') or emd.get('cc') or emd.get('bcc')), f"No recipients found in metadata: {emd}"
    assert emd.get('date'), f"No date found in metadata: {emd}"


def test_process_emails_endpoint_pst_feature_flag_behavior():
    # Without pypff installed, uploading a small .pst with accept_pst=true should return informative error and grouping keyword
    placeholder = b"!pst placeholder!"  # not a real PST
    files = {
        "files": ("emails.pst", BytesIO(placeholder), "application/octet-stream"),
    }
    with _client() as c:
        r = c.post(
            "/api/v1/media/process-emails",
            files=files,
            data={
                "accept_pst": "true",
            },
        )
        assert r.status_code in (200, 207)
        data = r.json()
        res = data.get("results") or []
        assert len(res) >= 1 and isinstance(res[0], dict)
        item = res[0]
        assert item.get("status") == "Error"
        assert "pst/ost support not enabled" in str(item.get("error", "")).lower()
        kws = item.get("keywords") or []
        assert "email_pst:emails" in kws, f"PST grouping keyword missing: {kws}"
import pytest
