from __future__ import annotations

from html import escape
from typing import Any, Dict, List

from tldw_Server_API.app.core.File_Artifacts.adapters.base import ExportResult, ValidationIssue


class HtmlTableAdapter:
    file_type = "html_table"
    export_formats = {"html"}

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        columns = payload.get("columns")
        rows = payload.get("rows")
        if columns is None or rows is None:
            raise ValueError("columns_and_rows_required")
        if not isinstance(columns, list) or not isinstance(rows, list):
            raise ValueError("columns_rows_must_be_lists")
        normalized_columns = [str(col) for col in columns]
        normalized_rows = []
        for row in rows:
            if isinstance(row, (list, tuple)):
                normalized_rows.append(list(row))
            else:
                raise ValueError("row_must_be_list")
        return {"columns": normalized_columns, "rows": normalized_rows}

    def validate(self, structured: Dict[str, Any]) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        columns = structured.get("columns")
        rows = structured.get("rows")
        if not isinstance(columns, list) or not columns:
            issues.append(ValidationIssue(code="columns_required", message="columns must be a non-empty list", path="columns"))
            return issues
        if not isinstance(rows, list):
            issues.append(ValidationIssue(code="rows_required", message="rows must be a list", path="rows"))
            return issues
        col_len = len(columns)
        for idx, row in enumerate(rows):
            if not isinstance(row, list):
                issues.append(ValidationIssue(code="row_invalid", message="row must be a list", path=f"rows[{idx}]"))
                continue
            if len(row) != col_len:
                issues.append(
                    ValidationIssue(
                        code="row_length_mismatch",
                        message="row length must match columns length",
                        path=f"rows[{idx}]",
                    )
                )
        if self._has_duplicate_columns(columns):
            issues.append(
                ValidationIssue(
                    code="duplicate_columns",
                    message="columns contain duplicates",
                    path="columns",
                    level="warning",
                )
            )
        return issues

    def export(self, structured: Dict[str, Any], *, format: str) -> ExportResult:
        if format != "html":
            raise ValueError("unsupported_format")
        columns = structured.get("columns") or []
        rows = structured.get("rows") or []
        head_cells = "".join(f"<th>{escape(str(col))}</th>" for col in columns)
        body_rows = []
        for row in rows:
            cells = "".join(f"<td>{escape(self._cell_text(val))}</td>" for val in row)
            body_rows.append(f"<tr>{cells}</tr>")
        body_html = "".join(body_rows)
        content = f"<table><thead><tr>{head_cells}</tr></thead><tbody>{body_html}</tbody></table>"
        data = content.encode("utf-8")
        return ExportResult(status="ready", content_type="text/html", bytes_len=len(data), content=data)

    @staticmethod
    def _cell_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).replace("\n", " ")

    @staticmethod
    def _has_duplicate_columns(columns: list[Any]) -> bool:
        seen = set()
        for col in columns:
            if col in seen:
                return True
            seen.add(col)
        return False
