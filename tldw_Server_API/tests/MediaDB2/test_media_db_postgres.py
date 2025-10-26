import os
import urllib.parse

import pytest
# Import required AuthNZ fixtures directly to make them available to this module
from tldw_Server_API.tests.AuthNZ.conftest import setup_test_database, clean_database  # noqa: F401

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.scope_context import scoped_context


TEST_RLS_ROLE = "tldw_rls_tester"


def _has_postgres_dependencies() -> bool:
    try:
        import psycopg  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install psycopg[binary])",
)
@pytest.mark.usefixtures("setup_test_database", "clean_database")
def test_media_rls_enforces_scope_postgres():
    dsn = (os.getenv("DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or "").strip()
    assert dsn, "Postgres test database URL not configured"

    base_config = DatabaseConfig.from_env()
    assert base_config.backend_type == BackendType.POSTGRESQL, "Expected PostgreSQL backend configuration"

    parsed = urllib.parse.urlparse(dsn)
    db_name = (parsed.path or "/").lstrip("/") or "postgres"
    host = parsed.hostname or "localhost"
    port = int(parsed.port or 5432)

    admin_backend = DatabaseBackendFactory.create_backend(base_config)
    bootstrap_db = MediaDatabase(db_path=":memory:", client_id="bootstrap", backend=admin_backend)
    test_role = TEST_RLS_ROLE
    test_password = "ContentRlsR3g!"
    ident = admin_backend.escape_identifier  # type: ignore[attr-defined]

    with admin_backend.transaction() as conn:
        admin_backend.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{test_role}'::text) THEN
                    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '{test_role}', '{test_password}');
                ELSE
                    EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', '{test_role}', '{test_password}');
                END IF;
            END$$;
            """,
            connection=conn,
        )
        admin_backend.execute(
            f"GRANT USAGE ON SCHEMA public TO {ident(test_role)}",
            connection=conn,
        )
        admin_backend.execute(
            f"GRANT CREATE ON SCHEMA public TO {ident(test_role)}",
            connection=conn,
        )
        admin_backend.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ident(test_role)}",
            connection=conn,
        )
        admin_backend.execute(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ident(test_role)}",
            connection=conn,
        )
        admin_backend.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {ident(test_role)}",
            connection=conn,
        )
        admin_backend.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {ident(test_role)}",
            connection=conn,
        )
        admin_backend.execute(
            f"GRANT {ident(test_role)} TO CURRENT_USER",
            connection=conn,
        )

    try:
        bootstrap_db.close_connection()
    except Exception:
        pass

    backend = admin_backend

    db_owner = MediaDatabase(db_path=":memory:", client_id="101", backend=backend)
    db_other_user = MediaDatabase(db_path=":memory:", client_id="202", backend=backend)
    db_admin = MediaDatabase(db_path=":memory:", client_id="999", backend=backend)
    db_team_owner = MediaDatabase(db_path=":memory:", client_id="303", backend=backend)
    db_team_reader = MediaDatabase(db_path=":memory:", client_id="404", backend=backend)
    db_org_owner = MediaDatabase(db_path=":memory:", client_id="606", backend=backend)
    db_org_member = MediaDatabase(db_path=":memory:", client_id="707", backend=backend)

    try:
        with scoped_context(
            user_id=101,
            org_ids=[],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            media_id, _, _ = db_owner.add_media_with_keywords(
                title="personal doc",
                content="sensitive content",
                media_type="text",
                chunks=None,
                keywords=[],
            )

        with scoped_context(
            user_id=202,
            org_ids=[],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            current_role = db_other_user.backend.execute("SELECT current_role").scalar
            assert current_role == TEST_RLS_ROLE
            current_scope = db_other_user.backend.execute(
                "SELECT current_setting('app.current_user_id', true)"
            ).scalar
            assert current_scope == "202"
            assert (
                db_other_user.get_media_by_id(media_id) is None
            ), "Unrelated user should not see another user's media"

        with scoped_context(
            user_id=101,
            org_ids=[],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            owner_row = db_owner.get_media_by_id(media_id)
            assert owner_row is not None and owner_row["id"] == media_id

        with scoped_context(
            user_id=999,
            org_ids=[],
            team_ids=[],
            is_admin=True,
        ):
            admin_row = db_admin.get_media_by_id(media_id)
            assert admin_row is not None and admin_row["id"] == media_id

        with scoped_context(
            user_id=606,
            org_ids=[12],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            org_media_id, _, _ = db_org_owner.add_media_with_keywords(
                title="org shared doc",
                content="org scope content",
                media_type="text",
                chunks=None,
                keywords=[],
            )

        with scoped_context(
            user_id=707,
            org_ids=[12],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            org_row = db_org_member.get_media_by_id(org_media_id)
            assert org_row is not None and org_row["id"] == org_media_id

        with scoped_context(
            user_id=808,
            org_ids=[],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            assert (
                db_other_user.get_media_by_id(org_media_id) is None
            ), "User without org membership should not see org media"

        with scoped_context(
            user_id=303,
            org_ids=[],
            team_ids=[77],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            team_media_id, _, _ = db_team_owner.add_media_with_keywords(
                title="team shared doc",
                content="shared content",
                media_type="text",
                chunks=None,
                keywords=[],
            )

        with scoped_context(
            user_id=505,
            org_ids=[],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            assert (
                db_other_user.get_media_by_id(team_media_id) is None
            ), "User without team membership should be denied"

        with scoped_context(
            user_id=404,
            org_ids=[],
            team_ids=[77],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            accessible = db_team_reader.get_media_by_id(team_media_id)
            assert accessible is not None and accessible["id"] == team_media_id

        with scoped_context(
            user_id=202,
            org_ids=[],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            update_attempt = db_other_user.backend.execute(
                "UPDATE media SET title = %s WHERE id = %s",
                ("malicious edit", media_id),
            )
            assert update_attempt.rowcount == 0

        with scoped_context(
            user_id=808,
            org_ids=[],
            team_ids=[],
            is_admin=False,
            session_role=TEST_RLS_ROLE,
        ):
            org_update_attempt = db_other_user.backend.execute(
                "UPDATE media SET title = %s WHERE id = %s",
                ("bad org edit", org_media_id),
            )
            assert org_update_attempt.rowcount == 0

        with scoped_context(user_id=999, org_ids=[], team_ids=[], is_admin=True):
            admin_update = db_admin.backend.execute(
                "UPDATE media SET title = %s WHERE id = %s",
                ("admin retitle", media_id),
            )
            assert admin_update.rowcount == 1
            updated = db_admin.get_media_by_id(media_id)
            assert updated is not None and updated["title"] == "admin retitle"

    finally:
        for db in (
            db_owner,
            db_other_user,
            db_admin,
            db_team_owner,
            db_team_reader,
            db_org_owner,
            db_org_member,
        ):
            try:
                db.close_connection()
            except Exception:
                pass
        try:
            backend.close_all()
        except Exception:
            pass
