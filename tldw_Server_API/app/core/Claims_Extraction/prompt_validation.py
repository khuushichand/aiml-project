from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from string import Formatter
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Claims_Extraction.alignment import align_claim
from tldw_Server_API.app.core.Claims_Extraction.runtime_config import (
    resolve_claims_prompt_validation_config,
)
from tldw_Server_API.app.core.Utils.prompt_loader import load_prompt

_CLAIMS_TEMPLATE_FORMAT_EXCEPTIONS = (
    KeyError,
    IndexError,
    TypeError,
    ValueError,
)

_DEFAULT_CLAIMS_PROMPT_TEMPLATE = (
    "Extract up to {max_claims} atomic factual propositions from the ANSWER. "
    "Each proposition should stand alone without the surrounding context, be specific and checkable. "
    "Return JSON: {{\"claims\":[{{\"text\": str}}]}}. Do not include explanations.\n\nANSWER:\n{answer}"
)

_DEFAULT_SAMPLE_SOURCE = (
    "Acme Corp reported annual revenue of 12 million dollars in 2024. "
    "The report states net margin improved to 18 percent."
)

_DEFAULT_SAMPLE_CLAIMS: tuple[str, ...] = (
    "Acme Corp reported annual revenue of 12 million dollars in 2024.",
    "net margin improved to 18 percent.",
)


@dataclass(frozen=True)
class ClaimsPromptValidationIssue:
    code: str
    message: str
    detail: str | None = None


@dataclass(frozen=True)
class ClaimsPromptValidationReport:
    mode: str
    strict: bool
    issues: tuple[ClaimsPromptValidationIssue, ...]

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


class ClaimsPromptValidationError(RuntimeError):
    """Raised when prompt preflight validation is configured to fail-fast."""


def _normalize_mode(mode: str | None, *, default: str = "warning") -> str:
    resolved = str(mode or default).strip().lower()
    if resolved not in {"off", "warning", "error"}:
        return default
    return resolved


def _extract_placeholders(template: str) -> set[str]:
    names: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if not field_name:
            continue
        base = str(field_name).split(".", 1)[0].split("[", 1)[0].strip()
        if base:
            names.add(base)
    return names


def _format_prompt_template(
    template: str,
    *,
    answer: str,
    max_claims: int,
) -> str:
    try:
        return template.format(answer=answer, max_claims=max_claims)
    except _CLAIMS_TEMPLATE_FORMAT_EXCEPTIONS:
        escaped = template.replace("{", "{{").replace("}", "}}")
        escaped = escaped.replace("{{answer}}", "{answer}").replace("{{max_claims}}", "{max_claims}")
        return escaped.format(answer=answer, max_claims=max_claims)


def validate_claims_prompt_template(
    prompt_template: str,
    *,
    mode: str = "warning",
    strict: bool = False,
    required_placeholders: Sequence[str] = ("answer", "max_claims"),
    sample_source_text: str = _DEFAULT_SAMPLE_SOURCE,
    sample_claim_texts: Sequence[str] = _DEFAULT_SAMPLE_CLAIMS,
) -> ClaimsPromptValidationReport:
    issues: list[ClaimsPromptValidationIssue] = []
    resolved_mode = _normalize_mode(mode)

    template = str(prompt_template or "").strip()
    if not template:
        issues.append(
            ClaimsPromptValidationIssue(
                code="empty_template",
                message="Claims extractor prompt template is empty.",
            )
        )
        return ClaimsPromptValidationReport(mode=resolved_mode, strict=bool(strict), issues=tuple(issues))

    try:
        placeholders = _extract_placeholders(template)
    except ValueError as exc:
        # Some templates include literal JSON braces without escaping.
        escaped = template.replace("{", "{{").replace("}", "}}")
        escaped = escaped.replace("{{answer}}", "{answer}").replace("{{max_claims}}", "{max_claims}")
        try:
            placeholders = _extract_placeholders(escaped)
        except ValueError:
            issues.append(
                ClaimsPromptValidationIssue(
                    code="placeholder_parse_error",
                    message="Claims prompt template has invalid placeholder syntax.",
                    detail=str(exc),
                )
            )
            placeholders = set()

    missing = [name for name in required_placeholders if str(name) not in placeholders]
    for name in missing:
        issues.append(
            ClaimsPromptValidationIssue(
                code="missing_placeholder",
                message=f"Claims prompt template is missing required placeholder '{{{name}}}'.",
                detail=f"present={sorted(placeholders)}",
            )
        )

    if not missing:
        try:
            _format_prompt_template(template, answer=sample_source_text, max_claims=max(1, len(sample_claim_texts)))
        except _CLAIMS_TEMPLATE_FORMAT_EXCEPTIONS as exc:
            issues.append(
                ClaimsPromptValidationIssue(
                    code="template_format_error",
                    message="Claims prompt template failed formatting with sample values.",
                    detail=str(exc),
                )
            )

    alignment_mode = "exact" if strict else "fuzzy"
    alignment_threshold = 0.99 if strict else 0.75
    for claim_text in sample_claim_texts:
        result = align_claim(
            sample_source_text,
            claim_text,
            mode=alignment_mode,
            threshold=alignment_threshold,
        )
        if result is None:
            issues.append(
                ClaimsPromptValidationIssue(
                    code="sample_alignment_failed",
                    message="Sample claim text did not align with sample source text.",
                    detail=claim_text,
                )
            )
            continue
        if strict and result.method != "exact":
            issues.append(
                ClaimsPromptValidationIssue(
                    code="sample_alignment_non_exact",
                    message="Strict prompt validation requires exact sample alignment.",
                    detail=f"method={result.method}; claim={claim_text}",
                )
            )

    return ClaimsPromptValidationReport(mode=resolved_mode, strict=bool(strict), issues=tuple(issues))


def handle_claims_prompt_validation_report(report: ClaimsPromptValidationReport) -> None:
    mode = _normalize_mode(report.mode)
    if mode == "off":
        return

    for issue in report.issues:
        logger.warning(
            "claims prompt validation [{}]: {}{}",
            issue.code,
            issue.message,
            f" ({issue.detail})" if issue.detail else "",
        )

    if mode == "error" and report.has_issues:
        first_issue = report.issues[0]
        raise ClaimsPromptValidationError(
            f"Claims prompt validation failed: {first_issue.code}: {first_issue.message}"
        )


def validate_claims_prompt_preflight(
    settings_obj: Mapping[str, Any] | None = None,
    *,
    mode: str | None = None,
    strict: bool | None = None,
) -> ClaimsPromptValidationReport:
    resolved_mode, resolved_strict = resolve_claims_prompt_validation_config(
        settings_obj,
        default_mode="warning",
        default_strict=False,
    )
    if mode is not None:
        resolved_mode = _normalize_mode(mode, default=resolved_mode)
    if strict is not None:
        resolved_strict = bool(strict)

    prompt_template = load_prompt("ingestion", "claims_extractor_prompt") or _DEFAULT_CLAIMS_PROMPT_TEMPLATE
    report = validate_claims_prompt_template(
        prompt_template,
        mode=resolved_mode,
        strict=resolved_strict,
    )
    handle_claims_prompt_validation_report(report)
    return report


__all__ = [
    "ClaimsPromptValidationError",
    "ClaimsPromptValidationIssue",
    "ClaimsPromptValidationReport",
    "handle_claims_prompt_validation_report",
    "validate_claims_prompt_preflight",
    "validate_claims_prompt_template",
]
