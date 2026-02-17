import uuid

import pytest

from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreakerConfig,
)
from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    registry as circuit_breaker_registry,
)
from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import (
    _admin_headers,
    _user_headers,
)

pytestmark = pytest.mark.integration


def _grant_system_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as user_db_handling

    original_get_effective_permissions = user_db_handling.get_effective_permissions

    def _patched_get_effective_permissions(user_id: int):
        perms = list(original_get_effective_permissions(user_id))
        if "system.logs" not in perms:
            perms.append("system.logs")
        return perms

    monkeypatch.setattr(
        user_db_handling,
        "get_effective_permissions",
        _patched_get_effective_permissions,
    )


def _strip_system_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as user_db_handling

    original_get_effective_permissions = user_db_handling.get_effective_permissions

    def _patched_get_effective_permissions(user_id: int):
        perms = list(original_get_effective_permissions(user_id))
        return [perm for perm in perms if perm != "system.logs"]

    monkeypatch.setattr(
        user_db_handling,
        "get_effective_permissions",
        _patched_get_effective_permissions,
    )


def _disable_admin_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps

    monkeypatch.setattr(
        auth_deps,
        "_principal_has_admin_bypass_claims",
        lambda _principal: False,
    )


def test_admin_circuit_breakers_list_and_filters(isolated_test_environment, monkeypatch):
    client, db_name = isolated_test_environment
    _disable_admin_bypass(monkeypatch)
    _grant_system_logs(monkeypatch)

    headers = _admin_headers(client, db_name)
    prefix = f"it-admin-cb-{uuid.uuid4().hex[:10]}"
    chat_name = f"{prefix}-chat"
    rag_name = f"{prefix}-rag"

    try:
        circuit_breaker_registry.get_or_create(
            chat_name,
            config=CircuitBreakerConfig(
                category="chat",
                service="openai",
                operation="completion",
                emit_metrics=False,
            ),
        )
        rag_breaker = circuit_breaker_registry.get_or_create(
            rag_name,
            config=CircuitBreakerConfig(
                category="rag",
                service="retrieval",
                operation="search",
                emit_metrics=False,
            ),
        )
        rag_breaker.force_open()

        list_response = client.get(
            "/api/v1/admin/circuit-breakers",
            headers=headers,
            params={"name_prefix": prefix},
        )
        assert list_response.status_code == 200, list_response.text
        payload = list_response.json()
        assert payload["total"] == 2
        assert [item["name"] for item in payload["items"]] == sorted([chat_name, rag_name])

        by_name = {item["name"]: item for item in payload["items"]}
        assert by_name[chat_name]["state"] == "CLOSED"
        assert by_name[chat_name]["category"] == "chat"
        assert by_name[chat_name]["service"] == "openai"
        assert by_name[chat_name]["operation"] == "completion"
        # When shared persistence is enabled, in-process breakers appear as
        # "mixed" (present in memory + persistent store). In memory-only mode,
        # they appear as "memory".
        assert by_name[chat_name]["source"] in {"memory", "mixed"}
        assert by_name[rag_name]["state"] == "OPEN"
        assert by_name[rag_name]["category"] == "rag"
        assert by_name[rag_name]["service"] == "retrieval"
        assert by_name[rag_name]["operation"] == "search"

        filtered_response = client.get(
            "/api/v1/admin/circuit-breakers",
            headers=headers,
            params={
                "name_prefix": prefix,
                "state": "CLOSED",
                "category": "chat",
                "service": "openai",
            },
        )
        assert filtered_response.status_code == 200, filtered_response.text
        filtered_payload = filtered_response.json()
        assert filtered_payload["total"] == 1
        assert filtered_payload["items"][0]["name"] == chat_name
    finally:
        circuit_breaker_registry.remove(chat_name)
        circuit_breaker_registry.remove(rag_name)


def test_admin_circuit_breakers_requires_admin_role(isolated_test_environment, monkeypatch):
    client, _db_name = isolated_test_environment
    _disable_admin_bypass(monkeypatch)
    _grant_system_logs(monkeypatch)
    headers = _user_headers(client, suffix=f"cb_{uuid.uuid4().hex[:8]}")

    response = client.get("/api/v1/admin/circuit-breakers", headers=headers)
    assert response.status_code == 403


def test_admin_circuit_breakers_requires_system_logs_permission(
    isolated_test_environment,
    monkeypatch,
):
    client, db_name = isolated_test_environment
    _disable_admin_bypass(monkeypatch)
    _strip_system_logs(monkeypatch)
    headers = _admin_headers(client, db_name)

    response = client.get("/api/v1/admin/circuit-breakers", headers=headers)
    assert response.status_code == 403
    assert "missing system.logs" in response.text
