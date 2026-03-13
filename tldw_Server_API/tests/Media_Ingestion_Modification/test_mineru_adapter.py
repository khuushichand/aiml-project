from __future__ import annotations

import json
import sys

import pytest


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


def test_run_mineru_document_ocr_executes_cli_and_returns_details(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        run_mineru_document_ocr,
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    script_path = tmp_path / "fake_mineru.py"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "import pathlib",
                "import sys",
                "",
                "args = sys.argv[1:]",
                "pdf_path = pathlib.Path(args[args.index('-p') + 1])",
                "out_dir = pathlib.Path(args[args.index('-o') + 1])",
                "run_dir = out_dir / pdf_path.stem",
                "run_dir.mkdir(parents=True, exist_ok=True)",
                "(run_dir / 'document.md').write_text('# Title\\n\\nBody', encoding='utf-8')",
                "(run_dir / 'content_list.json').write_text(json.dumps([{'page_idx': 0, 'text': 'Body'}]), encoding='utf-8')",
                "(run_dir / 'middle.json').write_text(json.dumps({'tables': [{'page': 1, 'html': '<table></table>'}]}), encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINERU_CMD", f"{sys.executable} {script_path}")
    monkeypatch.setenv("MINERU_TIMEOUT_SEC", "45")
    monkeypatch.setenv("MINERU_MAX_CONCURRENCY", "2")

    result = run_mineru_document_ocr(
        pdf_path=pdf_path,
        output_format="markdown",
        prompt_preset="table",
        requested_lang="eng",
        requested_dpi=300,
    )

    assert result["text"].startswith("# Title")
    assert result["structured"]["pages"][0]["page"] == 1
    assert result["details"]["backend"] == "mineru"
    assert result["details"]["timeout_sec"] == 45
    assert result["details"]["max_concurrency"] == 2
    assert result["details"]["ocr_pages"] == 1


def test_run_mineru_document_ocr_times_out(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        run_mineru_document_ocr,
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    script_path = tmp_path / "sleepy_mineru.py"
    script_path.write_text(
        "\n".join(
            [
                "import time",
                "time.sleep(2)",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINERU_CMD", f"{sys.executable} {script_path}")
    monkeypatch.setenv("MINERU_TIMEOUT_SEC", "1")

    with pytest.raises(TimeoutError, match="timed out"):
        run_mineru_document_ocr(pdf_path=pdf_path)
