import asyncio
import os
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Embeddings.audit_adapter import (
    emit_security_violation_async,
    emit_model_evicted_async,
    emit_memory_limit_exceeded_async,
)
from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService, AuditEventType
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


@pytest.mark.asyncio
async def test_security_violation_maps_to_unified_per_user(tmp_path):
    # Use a test user id and ensure DB path
    user_id = 4242
    db_path = DatabasePaths.get_audit_db_path(user_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Emit a security event
    await emit_security_violation_async(
        user_id=str(user_id),
        action="request_signature_invalid",
        metadata={"reason": "bad_sig"},
    )

    # Query events from the per-user audit DB
    svc = UnifiedAuditService(db_path=str(db_path))
    await svc.initialize()
    events = await svc.query_events(user_id=str(user_id))
    assert events, "Expected at least one audit event"
    # Find our event
    match = next(
        (
            e
            for e in events
            if e.get("event_type") == AuditEventType.SECURITY_VIOLATION.value
            and e.get("action") == "request_signature_invalid"
        ),
        None,
    )
    assert match is not None, "Security violation event not found"


@pytest.mark.asyncio
async def test_model_evicted_records_data_delete(tmp_path):
    # Default audit DB file path
    default_db = Path("./Databases/unified_audit.db")
    default_db.parent.mkdir(parents=True, exist_ok=True)

    model_id = "model-test-evict"
    await emit_model_evicted_async(model_id=model_id, memory_usage_gb=1.25, reason="lru_eviction")

    svc = UnifiedAuditService(db_path=str(default_db))
    await svc.initialize()
    events = await svc.query_events()
    assert events, "Expected events in default audit DB"
    match = next(
        (
            e
            for e in events
            if e.get("event_type") == AuditEventType.DATA_DELETE.value
            and e.get("resource_type") == "embedding_model"
            and e.get("resource_id") == model_id
            and e.get("action") == "model_evicted"
        ),
        None,
    )
    assert match is not None, "Model eviction event not found"


@pytest.mark.asyncio
async def test_memory_limit_exceeded_records_system_error(tmp_path):
    default_db = Path("./Databases/unified_audit.db")
    default_db.parent.mkdir(parents=True, exist_ok=True)

    model_id = "model-oom"
    await emit_memory_limit_exceeded_async(
        model_id=model_id,
        memory_usage_gb=2.5,
        current_usage_gb=6.0,
        limit_gb=8.0,
    )

    svc = UnifiedAuditService(db_path=str(default_db))
    await svc.initialize()
    events = await svc.query_events()
    assert events, "Expected events in default audit DB"
    match = next(
        (
            e
            for e in events
            if e.get("event_type") == AuditEventType.SYSTEM_ERROR.value
            and e.get("resource_type") == "embedding_model"
            and e.get("resource_id") == model_id
            and e.get("action") == "embeddings_memory_limit_exceeded"
        ),
        None,
    )
    assert match is not None, "Memory limit exceeded event not found"
