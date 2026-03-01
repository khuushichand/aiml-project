import pytest

from tldw_Server_API.app.core.Audio.dictation_error_taxonomy import (
    DictationErrorClass,
    build_dictation_error_payload,
    classify_dictation_error,
    dictation_error_allows_auto_fallback,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status_code", "detail", "expected"),
    [
        (401, {"message": "Unauthorized"}, DictationErrorClass.AUTH_ERROR),
        (403, {"status": "forbidden"}, DictationErrorClass.AUTH_ERROR),
        (402, {"message": "quota exceeded"}, DictationErrorClass.QUOTA_ERROR),
        (429, {"status": "rate_limited"}, DictationErrorClass.QUOTA_ERROR),
        (503, {"status": "provider_unavailable"}, DictationErrorClass.PROVIDER_UNAVAILABLE),
        (503, {"status": "model_downloading"}, DictationErrorClass.MODEL_UNAVAILABLE),
        (500, {"status": "transient_failure"}, DictationErrorClass.TRANSIENT_FAILURE),
        (500, {"status": "empty_transcript"}, DictationErrorClass.EMPTY_TRANSCRIPT),
        (500, {"status": "permission_denied"}, DictationErrorClass.PERMISSION_DENIED),
        (500, {"status": "unsupported_api"}, DictationErrorClass.UNSUPPORTED_API),
    ],
)
def test_classify_dictation_error_by_status(status_code, detail, expected):
    result = classify_dictation_error(status_code=status_code, detail=detail)
    assert result == expected


@pytest.mark.unit
def test_classify_dictation_error_from_message_keywords():
    result = classify_dictation_error(
        status_code=500,
        detail={"message": "The transcription did not return any text."},
    )
    assert result == DictationErrorClass.EMPTY_TRANSCRIPT


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error_class", "expected"),
    [
        (DictationErrorClass.UNSUPPORTED_API, True),
        (DictationErrorClass.PROVIDER_UNAVAILABLE, True),
        (DictationErrorClass.MODEL_UNAVAILABLE, True),
        (DictationErrorClass.TRANSIENT_FAILURE, True),
        (DictationErrorClass.AUTH_ERROR, False),
        (DictationErrorClass.QUOTA_ERROR, False),
        (DictationErrorClass.PERMISSION_DENIED, False),
        (DictationErrorClass.EMPTY_TRANSCRIPT, False),
        (DictationErrorClass.UNKNOWN_ERROR, False),
    ],
)
def test_dictation_fallback_policy(error_class, expected):
    assert dictation_error_allows_auto_fallback(error_class) is expected


@pytest.mark.unit
def test_build_dictation_error_payload_includes_taxonomy_fields():
    payload = build_dictation_error_payload(
        status_code=503,
        status="provider_unavailable",
        message="Provider unavailable",
        extra={"provider": "external"},
    )
    assert payload["status"] == "provider_unavailable"
    assert payload["provider"] == "external"
    assert payload["dictation_error_class"] == DictationErrorClass.PROVIDER_UNAVAILABLE.value
    assert payload["dictation_fallback_allowed"] is True
