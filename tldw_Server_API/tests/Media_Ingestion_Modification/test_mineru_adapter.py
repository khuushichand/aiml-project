from __future__ import annotations

import json


def test_build_mineru_command_returns_argv_tokens(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        _build_mineru_command,
    )

    pdf_path = tmp_path / "sample.pdf"
    out_dir = tmp_path / "out"
    monkeypatch.setenv("MINERU_CMD", "mineru")

    cmd = _build_mineru_command(pdf_path=pdf_path, output_dir=out_dir)

    assert isinstance(cmd, list)
    assert all(isinstance(part, str) for part in cmd)
    assert cmd[0] == "mineru"
    assert str(pdf_path) in cmd
    assert str(out_dir) in cmd


def test_normalize_mineru_output_returns_versioned_bounded_payload(tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        _normalize_mineru_output_dir,
    )

    out_dir = tmp_path / "mineru-out"
    out_dir.mkdir()
    (out_dir / "document.md").write_text("# Title\n\n|A|B|\n|-|-|\n|1|2|\n", encoding="utf-8")
    (out_dir / "content_list.json").write_text(
        json.dumps(
            [
                {"page_idx": 0, "type": "text", "text": "page one"},
                {"page_idx": 1, "type": "text", "text": "page two"},
            ]
        ),
        encoding="utf-8",
    )
    (out_dir / "middle.json").write_text(
        json.dumps(
            {
                "tables": [
                    {"page": 1, "html": "<table><tr><td>1</td></tr></table>"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = _normalize_mineru_output_dir(
        out_dir,
        output_format="markdown",
        prompt_preset="table",
    )

    assert result["text"].startswith("# Title")
    structured = result["structured"]
    assert structured["schema_version"] == 1
    assert structured["format"] == "markdown"
    assert structured["pages"][0]["page"] == 1
    assert structured["pages"][0]["text"] == "page one"
    assert structured["tables"][0]["format"] == "html"
    assert structured["tables"][0]["content"].startswith("<table>")
    assert "content_list_excerpt" in structured["artifacts"]
    assert "middle_json_excerpt" in structured["artifacts"]
