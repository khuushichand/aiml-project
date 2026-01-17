from __future__ import annotations

from typing import Any, Dict, List, NoReturn

from tldw_Server_API.app.core.File_Artifacts.adapters.base import ValidationIssue


class TableAdapterBase:
    """Shared normalization and validation for table-based file artifacts."""

    validation_error: type[Exception] = ValueError

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        columns = payload.get("columns")
        rows = payload.get("rows")
        if columns is None or rows is None:
            self._raise_validation_error("columns_and_rows_required")
        if not isinstance(columns, list) or not isinstance(rows, list):
            self._raise_validation_error("columns_rows_must_be_lists")
        normalized_columns = [str(col) for col in columns]
        normalized_rows = []
        for row in rows:
            if isinstance(row, (list, tuple)):
                normalized_rows.append(list(row))
            else:
                self._raise_validation_error("row_must_be_list")
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

    def _raise_validation_error(self, code: str) -> NoReturn:
        raise self.validation_error(code)

    @staticmethod
    def _has_duplicate_columns(columns: list[Any]) -> bool:
        seen = set()
        for col in columns:
            if col in seen:
                return True
            seen.add(col)
        return False
