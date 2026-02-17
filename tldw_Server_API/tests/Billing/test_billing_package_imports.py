from __future__ import annotations

import importlib


def test_billing_repo_import_does_not_circular() -> None:
    """billing_repo should import cleanly without package-level cycles."""
    module = importlib.import_module("tldw_Server_API.app.core.AuthNZ.repos.billing_repo")
    assert hasattr(module, "AuthnzBillingRepo")


def test_billing_package_lazy_subscription_exports() -> None:
    """Billing package should lazily expose subscription service symbols."""
    module = importlib.import_module("tldw_Server_API.app.core.Billing")
    assert callable(getattr(module, "get_subscription_service"))


def test_pg_billing_table_ensure_includes_runtime_tables() -> None:
    """Postgres billing ensure helper should include webhook/payment/audit tables."""
    module = importlib.import_module("tldw_Server_API.app.core.AuthNZ.pg_migrations_extra")
    ddl_statements = " ".join(
        sql.lower()
        for sql, _params in getattr(module, "_CREATE_BILLING_TABLES")
    )
    assert "create table if not exists stripe_webhook_events" in ddl_statements
    assert "create table if not exists payment_history" in ddl_statements
    assert "create table if not exists billing_audit_log" in ddl_statements
