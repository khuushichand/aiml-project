from __future__ import annotations

import pytest

from tldw_Server_API.app.core.External_Sources import connectors_service as svc
from tldw_Server_API.app.core.External_Sources.sync_adapter import (
    FileSyncAdapter,
    FileSyncChange,
)


@pytest.mark.unit
def test_file_sync_change_normalizes_required_fields() -> None:
    change = FileSyncChange(
        event_type="content_updated",
        remote_id="abc123",
        remote_name="report.pdf",
    )

    assert change.event_type == "content_updated"
    assert change.remote_id == "abc123"
    assert change.remote_name == "report.pdf"


@pytest.mark.unit
def test_get_file_sync_connector_by_name_restricts_to_file_sync_providers() -> None:
    connector = svc.get_file_sync_connector_by_name("drive")

    assert connector.name == "drive"
    assert isinstance(connector, FileSyncAdapter)

    with pytest.raises(ValueError, match="does not support file sync"):
        svc.get_file_sync_connector_by_name("gmail")
