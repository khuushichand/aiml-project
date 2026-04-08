from __future__ import annotations

from tldw_Server_API.app.api.v1.endpoints.admin import admin_monitoring as admin_monitoring_mod


class _StubMonitoringDb:
    def __init__(self, row):
        self.row = row
        self.lookups: list[int] = []

    def get_alert(self, alert_id: int):
        self.lookups.append(alert_id)
        return self.row


def test_warn_if_runtime_alert_identity_missing_logs_warning(monkeypatch) -> None:
    db = _StubMonitoringDb(row=None)
    warnings: list[str] = []
    monkeypatch.setattr(
        admin_monitoring_mod.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )

    admin_monitoring_mod._warn_if_overlay_identity_has_no_runtime_row("alert:77", db)

    assert db.lookups == [77]
    assert any("missing runtime alert" in msg for msg in warnings)


def test_warn_if_overlay_only_identity_logs_info_without_lookup(monkeypatch) -> None:
    db = _StubMonitoringDb(row=None)
    infos: list[str] = []
    monkeypatch.setattr(
        admin_monitoring_mod.logger,
        "info",
        lambda message, *args, **kwargs: infos.append(str(message)),
    )

    admin_monitoring_mod._warn_if_overlay_identity_has_no_runtime_row("fingerprint:abc", db)

    assert db.lookups == []
    assert any("overlay-only identity" in msg for msg in infos)


def test_warn_if_malformed_runtime_alert_identity_logs_warning(monkeypatch) -> None:
    db = _StubMonitoringDb(row=None)
    warnings: list[str] = []
    monkeypatch.setattr(
        admin_monitoring_mod.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )

    admin_monitoring_mod._warn_if_overlay_identity_has_no_runtime_row("alert:not-an-int", db)

    assert db.lookups == []
    assert any("malformed runtime alert identity" in msg for msg in warnings)
