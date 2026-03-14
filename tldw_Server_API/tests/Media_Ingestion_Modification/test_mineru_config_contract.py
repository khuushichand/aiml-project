from __future__ import annotations


def test_describe_mineru_backend_reports_configured_mode(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        describe_mineru_backend,
    )

    monkeypatch.setenv("MINERU_CMD", "mineru")
    monkeypatch.setenv("MINERU_TIMEOUT_SEC", "45")
    monkeypatch.setenv("MINERU_MAX_CONCURRENCY", "2")

    info = describe_mineru_backend()

    assert info["mode"] == "cli"
    assert info["pdf_only"] is True
    assert info["opt_in_only"] is True
    assert info["timeout_sec"] == 45
    assert info["max_concurrency"] == 2
