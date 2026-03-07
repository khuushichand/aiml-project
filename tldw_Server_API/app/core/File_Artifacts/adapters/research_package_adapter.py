"""Adapter for exported deep research packages."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from tldw_Server_API.app.core.exceptions import FileArtifactsValidationError
from tldw_Server_API.app.core.File_Artifacts.adapters.base import ExportResult, ValidationIssue


class ResearchPackageAdapter:
    """Export deep research packages as Markdown or JSON."""

    file_type: ClassVar[str] = "research_package"
    export_formats: ClassVar[set[str]] = {"json", "md"}

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(payload)

    def validate(self, structured: dict[str, Any]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not str(structured.get("report_markdown") or "").strip():
            issues.append(ValidationIssue(code="report_missing", message="report_markdown is required", path="report_markdown"))
        for index, claim in enumerate(structured.get("claims") or []):
            citations = claim.get("citations") if isinstance(claim, dict) else None
            if not citations:
                issues.append(
                    ValidationIssue(
                        code="claim_missing_citations",
                        message="Each claim must include at least one citation",
                        path=f"claims[{index}].citations",
                    )
                )
        return issues

    def export(self, structured: dict[str, Any], *, format: str) -> ExportResult:
        if format == "json":
            data = json.dumps(structured, indent=2, ensure_ascii=True, sort_keys=True).encode("utf-8")
            return ExportResult(status="ready", content_type="application/json", bytes_len=len(data), content=data)
        if format == "md":
            markdown = str(structured.get("report_markdown") or "")
            data = markdown.encode("utf-8")
            return ExportResult(status="ready", content_type="text/markdown", bytes_len=len(data), content=data)
        raise FileArtifactsValidationError("unsupported_format")
