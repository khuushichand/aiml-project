import pytest

from tldw_Server_API.app.core.Text2SQL.connectors import ConnectorRegistry


def test_connector_lookup_by_id_only() -> None:
    registry = ConnectorRegistry({"finance_warehouse": {"dialect": "postgresql"}})
    cfg = registry.get("finance_warehouse")
    assert cfg["dialect"] == "postgresql"


def test_connector_lookup_rejects_unknown_id() -> None:
    registry = ConnectorRegistry({})
    with pytest.raises(KeyError):
        registry.get("postgresql://raw-dsn-not-allowed")
