from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Dict, List

from tldw_Server_API.app.core.File_Artifacts.adapters.base import ExportResult, ValidationIssue
from tldw_Server_API.app.core.File_Artifacts.adapters.xlsx_adapter import XlsxAdapter


class DataTableAdapter:
    file_type = "data_table"
    export_formats = {"csv", "json", "xlsx"}

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
        if format == "csv":
            return self._export_csv(structured)
        if format == "json":
            return self._export_json(structured)
        if format == "xlsx":
            return self._export_xlsx(structured)
        raise ValueError("unsupported_format")

    def _export_csv(self, structured: Dict[str, Any]) -> ExportResult:
        columns = structured.get("columns") or []
        rows = structured.get("rows") or []
        buf = StringIO(newline="")
        writer = csv.writer(buf)
        writer.writerow([self._sanitize_cell(c) for c in columns])
        for row in rows:
            writer.writerow([self._sanitize_cell(c) for c in row])
        data = buf.getvalue().encode("utf-8")
        return ExportResult(status="ready", content_type="text/csv", bytes_len=len(data), content=data)

    def _export_json(self, structured: Dict[str, Any]) -> ExportResult:
        columns = structured.get("columns") or []
        rows = structured.get("rows") or []
        payload = [dict(zip(columns, row)) for row in rows]
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        return ExportResult(status="ready", content_type="application/json", bytes_len=len(data), content=data)

    def _export_xlsx(self, structured: Dict[str, Any]) -> ExportResult:
        columns = structured.get("columns") or []
        rows = structured.get("rows") or []
        adapter = XlsxAdapter()
        normalized = adapter.normalize({"columns": columns, "rows": rows})
        return adapter.export(normalized, format="xlsx")

    @staticmethod
    def _sanitize_cell(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).replace("\n", " ")
        stripped = text.lstrip()
        if stripped.startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    @staticmethod
    def _has_duplicate_columns(columns: list[Any]) -> bool:
        seen = set()
        for col in columns:
            if col in seen:
                return True
            seen.add(col)
        return False
