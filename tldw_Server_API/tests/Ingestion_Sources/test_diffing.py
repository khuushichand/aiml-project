from __future__ import annotations

import pytest


@pytest.mark.unit
def test_diff_snapshots_strips_single_archive_root_and_detects_change():
    from tldw_Server_API.app.core.Ingestion_Sources.diffing import (
        diff_snapshots,
        normalize_archive_members,
    )

    old_items = normalize_archive_members(
        ["export_1/notes/a.md"],
        {"export_1/notes/a.md": "hash-1"},
    )
    new_items = normalize_archive_members(
        ["export_2/notes/a.md"],
        {"export_2/notes/a.md": "hash-2"},
    )

    diff = diff_snapshots(previous=old_items, current=new_items)

    assert [item["relative_path"] for item in diff["changed"]] == ["notes/a.md"]
    assert diff["created"] == []
    assert diff["deleted"] == []
