"""Markdown table adapter for File Artifacts exports."""

from __future__ import annotations

from typing import Any, ClassVar

from tldw_Server_API.app.core.exceptions import FileArtifactsValidationError
from tldw_Server_API.app.core.File_Artifacts.adapters.base import ExportResult
from tldw_Server_API.app.core.File_Artifacts.adapters.table_adapter_base import TableAdapterBase


class MarkdownTableAdapter(TableAdapterBase):
    """Adapter for markdown_table payloads with Markdown exports."""

    file_type: ClassVar[str] = "markdown_table"
    export_formats: ClassVar[set[str]] = {"md"}
    validation_error: ClassVar[type[Exception]] = FileArtifactsValidationError

    def export(self, structured: dict[str, Any], *, format: str) -> ExportResult:
        """Export structured table content to Markdown."""
        if format != "md":
            raise FileArtifactsValidationError("unsupported_format")
        columns = structured.get("columns") or []
        rows = structured.get("rows") or []
        header = "| " + " | ".join(self._escape_cell(c) for c in columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        body_lines = []
        for row in rows:
            body_lines.append("| " + " | ".join(self._escape_cell(c) for c in row) + " |")
        content = "\n".join([header, separator] + body_lines) + "\n"
        data = content.encode("utf-8")
        return ExportResult(status="ready", content_type="text/markdown", bytes_len=len(data), content=data)

    @staticmethod
    def _escape_cell(value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        text = text.replace("\n", " ")
        return text.replace("|", "\\|")
