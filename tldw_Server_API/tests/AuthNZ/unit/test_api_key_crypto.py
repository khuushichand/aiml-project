import pytest

from tldw_Server_API.app.core.AuthNZ import api_key_crypto as ak


pytestmark = pytest.mark.unit


def test_parse_api_key_extracts_kid_and_secret() -> None:
    key_id = "deadbeefcafe"
    secret = "secret-part"
    api_key = ak.format_api_key(key_id, secret)

    parsed = ak.parse_api_key(api_key)

    assert parsed == (key_id, secret)


def test_parse_api_key_rejects_legacy_format() -> None:
    assert ak.parse_api_key("tldw_legacy_key_without_separator") is None
    assert ak.parse_api_key("not_a_tldw_key") is None


def test_kdf_roundtrip_verifies() -> None:
    api_key = "tldw_deadbeefcafe.secret"
    encoded = ak.kdf_hash_api_key(api_key, salt=b"fixed-salt-123456")

    assert ak.is_kdf_hash(encoded)
    assert ak.verify_kdf_hash(api_key, encoded) is True
    assert ak.verify_kdf_hash("tldw_deadbeefcafe.wrong", encoded) is False
