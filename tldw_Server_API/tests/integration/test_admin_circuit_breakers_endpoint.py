import uuid

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreakerConfig,
)
from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    registry as circuit_breaker_registry,
)


def test_admin_circuit_breakers_list_and_filters(client_user_only: TestClient):
    prefix = f"it-admin-cb-ui-{uuid.uuid4().hex[:10]}"
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

        resp = client_user_only.get(
            "/api/v1/admin/circuit-breakers",
            params={"name_prefix": prefix},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["total"] == 2
        assert [item["name"] for item in payload["items"]] == sorted([chat_name, rag_name])

        filtered = client_user_only.get(
            "/api/v1/admin/circuit-breakers",
            params={
                "name_prefix": prefix,
                "state": "CLOSED",
                "category": "chat",
                "service": "openai",
            },
        )
        assert filtered.status_code == 200, filtered.text
        filtered_payload = filtered.json()
        assert filtered_payload["total"] == 1
        assert filtered_payload["items"][0]["name"] == chat_name
    finally:
        circuit_breaker_registry.remove(chat_name)
        circuit_breaker_registry.remove(rag_name)
