from __future__ import annotations

import importlib
from datetime import datetime, timezone


def test_system_log_file_query_reads_shared_file(tmp_path, monkeypatch):
    log_path = tmp_path / "system_logs.jsonl"
    monkeypatch.setenv("SYSTEM_LOG_FILE_ENABLED", "true")
    monkeypatch.setenv("SYSTEM_LOG_FILE_PATH", str(log_path))
    monkeypatch.setenv("SYSTEM_LOG_FILE_MAX_ENTRIES", "10")

    import tldw_Server_API.app.core.Logging.system_log_buffer as log_buffer

    importlib.reload(log_buffer)

    entry = {
        "timestamp": datetime.now(timezone.utc),
        "level": "INFO",
        "message": "file-backed entry",
        "logger": "test",
        "module": "test_module",
        "function": "test_fn",
        "line": 1,
    }

    log_buffer._append_log_file(entry)

    items, total = log_buffer.query_system_logs(limit=10, offset=0)
    assert total >= 1
    assert any(item.get("message") == "file-backed entry" for item in items)
    assert log_path.exists()
