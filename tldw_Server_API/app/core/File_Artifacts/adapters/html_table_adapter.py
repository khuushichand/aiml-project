from __future__ import annotations

from html import escape
from typing import Any, Dict

from tldw_Server_API.app.core.File_Artifacts.adapters.base import ExportResult
from tldw_Server_API.app.core.File_Artifacts.adapters.table_adapter_base import TableAdapterBase


class HtmlTableAdapter(TableAdapterBase):
    file_type = "html_table"
    export_formats = {"html"}

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
