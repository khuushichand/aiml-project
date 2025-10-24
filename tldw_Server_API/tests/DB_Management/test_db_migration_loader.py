from pathlib import Path

from tldw_Server_API.app.core.DB_Management.db_migration import DatabaseMigrator


def test_load_migrations_includes_sql_baseline(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    migrations_dir = project_root / "app" / "core" / "DB_Management" / "migrations"

    db_path = tmp_path / "dummy.db"
    db_path.touch()

    migrator = DatabaseMigrator(str(db_path), str(migrations_dir))
    migrations = migrator.load_migrations()

    versions = [migration.version for migration in migrations]

    assert versions == sorted(versions)
    assert 1 in versions  # SQL baseline migration
    assert 5 in versions  # Last SQL migration
    assert versions.count(3) == 1  # duplicate SQL file is ignored
