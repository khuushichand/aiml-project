from __future__ import annotations

import pytest

from tldw_Server_API.app.services.admin_system_ops_service import _normalize_incident_record


pytestmark = pytest.mark.unit


def test_normalize_incident_record_leaves_resolution_metrics_empty_for_unresolved_incident() -> None:
    normalized = _normalize_incident_record(
        {
            "id": "incident-1",
            "created_at": "2026-03-01T00:00:00+00:00",
            "resolved_at": None,
            "timeline": [],
        }
    )

    assert normalized["time_to_acknowledge_seconds"] is None
    assert normalized["time_to_resolve_seconds"] is None


def test_normalize_incident_record_skips_seed_creation_event_for_acknowledgement() -> None:
    normalized = _normalize_incident_record(
        {
            "id": "incident-2",
            "created_at": "2026-03-01T00:00:00+00:00",
            "resolved_at": None,
            "timeline": [
                {
                    "id": "evt-seed",
                    "message": "Incident created",
                    "created_at": "2026-03-01T00:00:00+00:00",
                },
                {
                    "id": "evt-followup",
                    "message": "Investigating",
                    "created_at": "2026-03-01T00:05:00+00:00",
                },
            ],
        }
    )

    assert normalized["time_to_acknowledge_seconds"] == 300
