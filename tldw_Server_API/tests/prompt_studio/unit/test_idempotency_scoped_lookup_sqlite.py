import uuid
import pytest


pytestmark = pytest.mark.unit


def test_idempotency_lookup_scoped_by_user_sqlite(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db
    if label != "sqlite":
        pytest.skip("SQLite-specific lookup test")

    # Create a project to use as entity
    proj = db.create_project(name=f"ScopeProj-{uuid.uuid4().hex[:6]}", status="active")
    key = f"scope-{uuid.uuid4().hex}"

    # Record idempotency for userA
    db.record_idempotency("project", key, int(proj["id"]), "userA")

    # Lookup as userA -> should resolve
    found_a = db.lookup_idempotency("project", key, "userA")
    assert found_a == int(proj["id"])

    # Lookup as userB -> should not resolve
    found_b = db.lookup_idempotency("project", key, "userB")
    assert found_b is None

    # Recording the same key for userB should now succeed (per-user uniqueness)
    db.record_idempotency("project", key, 424242, "userB")
    found_b2 = db.lookup_idempotency("project", key, "userB")
    assert found_b2 == 424242
