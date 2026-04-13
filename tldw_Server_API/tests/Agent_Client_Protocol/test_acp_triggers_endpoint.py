from tldw_Server_API.app.api.v1.endpoints.acp_triggers import _sanitize_webhook_error_detail


def test_sanitize_webhook_error_detail_preserves_known_client_errors() -> None:
    status_code, detail = _sanitize_webhook_error_detail(
        {"status": "rejected", "error": "verification_failed"}
    )

    assert status_code == 403
    assert detail == {"status": "rejected", "error": "verification_failed"}


def test_sanitize_webhook_error_detail_hides_internal_failures() -> None:
    status_code, detail = _sanitize_webhook_error_detail(
        {"status": "error", "error": "submission_failed: stack trace details"}
    )

    assert status_code == 503
    assert detail == {"status": "error", "error": "internal_error"}


def test_sanitize_webhook_error_detail_hides_secret_decryption_failures() -> None:
    status_code, detail = _sanitize_webhook_error_detail(
        {"status": "error", "error": "secret_decryption_failed: decrypt failed"}
    )

    assert status_code == 503
    assert detail == {"status": "error", "error": "internal_error"}
