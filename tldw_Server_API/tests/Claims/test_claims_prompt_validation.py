import pytest

from tldw_Server_API.app.core.exceptions import ValidationError
from tldw_Server_API.app.core.Claims_Extraction.prompt_validation import (
    ClaimsPromptValidationError,
    claims_prompt_report_has_issues,
    validate_claims_prompt_preflight,
    validate_claims_prompt_template,
)


@pytest.mark.unit
def test_validate_claims_prompt_template_reports_missing_required_placeholders() -> None:
    """Verify that missing required placeholders are reported."""
    report = validate_claims_prompt_template(
        "Extract up to {max_claims} claims and return JSON.",
        mode="warning",
        strict=False,
    )
    codes = [issue.code for issue in report.issues]
    assert "missing_placeholder" in codes


@pytest.mark.unit
def test_claims_prompt_validation_error_uses_project_validation_hierarchy():
    assert issubclass(ClaimsPromptValidationError, ValidationError)


@pytest.mark.unit
def test_validate_claims_prompt_preflight_warning_mode_does_not_raise(monkeypatch) -> None:
    """Verify warning-mode preflight returns issues without raising."""
    import tldw_Server_API.app.core.Claims_Extraction.prompt_validation as prompt_validation

    monkeypatch.setattr(
        prompt_validation,
        "load_prompt",
        lambda _module, _key: "Extract up to {max_claims} claims and return JSON.",
    )

    report = validate_claims_prompt_preflight(
        {
            "CLAIMS_PROMPT_VALIDATION_MODE": "warning",
            "CLAIMS_PROMPT_VALIDATION_STRICT": False,
        }
    )
    assert report.has_issues


@pytest.mark.unit
def test_validate_claims_prompt_preflight_error_mode_raises(monkeypatch) -> None:
    """Verify error-mode preflight raises ClaimsPromptValidationError."""
    import tldw_Server_API.app.core.Claims_Extraction.prompt_validation as prompt_validation

    monkeypatch.setattr(
        prompt_validation,
        "load_prompt",
        lambda _module, _key: "Extract up to {max_claims} claims and return JSON.",
    )

    with pytest.raises(ClaimsPromptValidationError):
        validate_claims_prompt_preflight(
            {
                "CLAIMS_PROMPT_VALIDATION_MODE": "error",
                "CLAIMS_PROMPT_VALIDATION_STRICT": False,
            }
        )


@pytest.mark.unit
def test_validate_claims_prompt_template_strict_mode_flags_non_exact_alignment() -> None:
    """Verify strict mode flags sample alignment failures."""
    report = validate_claims_prompt_template(
        "Extract from {answer} and return up to {max_claims} claims.",
        mode="warning",
        strict=True,
        sample_source_text="state-of-the-art methods are common.",
        sample_claim_texts=["state of the art methods are common"],
    )
    codes = [issue.code for issue in report.issues]
    assert "sample_alignment_failed" in codes


@pytest.mark.unit
def test_claims_prompt_report_has_issues_handles_property_and_callable_shapes() -> None:
    """Verify has_issues supports property-style and callable-style reports."""

    class _PropertyStyleReport:
        @property
        def has_issues(self) -> bool:
            return True

    class _CallableStyleReport:
        def has_issues(self) -> bool:
            return True

    class _FalseStyleReport:
        has_issues = False

    assert claims_prompt_report_has_issues(_PropertyStyleReport()) is True
    assert claims_prompt_report_has_issues(_CallableStyleReport()) is True
    assert claims_prompt_report_has_issues(_FalseStyleReport()) is False
