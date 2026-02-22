from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager


def test_extract_token_metadata_handles_non_jwt_token() -> None:
    jti, expires_at = SessionManager._extract_token_metadata("temp_access_example_token")

    assert jti is None
    assert expires_at is None


def test_get_unverified_claims_handles_non_jwt_token() -> None:
    claims = SessionManager._get_unverified_claims("temp_refresh_example_token")

    assert claims is None
