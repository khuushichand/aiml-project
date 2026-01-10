import uuid
import pytest


pytestmark = pytest.mark.integration


def test_idempotency_lookup_scoped_by_user_postgres(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db
    if label != "postgres":
        pytest.skip("Postgres-specific idempotency test")

    proj = db.create_project(name=f"PGScope-{uuid.uuid4().hex[:6]}", status="active")
    key = f"pgscope-{uuid.uuid4().hex}"

    # Record mapping for userA
    db.record_idempotency("project", key, int(proj["id"]), "userA")

    # Lookup for userA resolves
    got_a = db.lookup_idempotency("project", key, "userA")
    assert got_a == int(proj["id"])

    # Lookup for userB does not resolve (scoped)
    got_b = db.lookup_idempotency("project", key, "userB")
    assert got_b is None

    # Recording the same key for userB should succeed under per-user uniqueness
    db.record_idempotency("project", key, 999999, "userB")
    got_b2 = db.lookup_idempotency("project", key, "userB")
    assert got_b2 == 999999
