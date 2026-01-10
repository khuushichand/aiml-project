import base64

import pytest

from tldw_Server_API.app.core.Security import crypto


@pytest.mark.skipif(not crypto._HAS_CRYPTO, reason="Crypto backend not available")
def test_decrypt_json_blob_invalid_base64_returns_none(monkeypatch):
    key = base64.b64encode(b"a" * 32).decode("ascii")
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_ENC_KEY", key)
    envelope = {"_enc": "aesgcm:v1", "nonce": "abc", "ct": "abc", "tag": "abc"}
    assert crypto.decrypt_json_blob(envelope) is None


@pytest.mark.skipif(not crypto._HAS_CRYPTO, reason="Crypto backend not available")
def test_decrypt_json_blob_with_key_invalid_base64_returns_none():
    key = base64.b64encode(b"b" * 32).decode("ascii")
    envelope = {"_enc": "aesgcm:v1", "nonce": "abc", "ct": "abc", "tag": "abc"}
    assert crypto.decrypt_json_blob_with_key(envelope, key) is None
