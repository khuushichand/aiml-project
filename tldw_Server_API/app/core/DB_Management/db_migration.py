# db_migration.py - Database Migration System
"""
Database migration system for tldw_server.

This module provides:
- Schema version tracking
- Migration execution (up/down)
- Backup before migration
- Rollback capabilities
- Migration history tracking

Based on ADR-002: Alembic-style migrations within SQLite constraints.
"""

import os
import re
import sqlite3
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from contextlib import contextmanager



class MigrationError(Exception):
    """Base exception for migration errors"""
    pass


class Migration:
    """Represents a single database migration"""

    def __init__(
        self,
        version: int,
        name: str,
        up_sql: str,
        down_sql: Optional[str] = None,
        description: str = ""
    ):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.description = description
        self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate checksum for migration integrity"""
        import hashlib
        content = f"{self.version}:{self.name}:{self.up_sql}:{self.down_sql or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert migration to dictionary"""
        return {
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "checksum": self.checksum,
            "up_sql": self.up_sql,
            "down_sql": self.down_sql
        }

    @classmethod
    def from_file(cls, filepath: Path) -> 'Migration':
        """Load migration from file"""
        with open(filepath, 'r') as f:
            data = json.load(f)

        return cls(
            version=data["version"],
            name=data["name"],
            up_sql=data["up_sql"],
            down_sql=data.get("down_sql"),
            description=data.get("description", "")
        )


class DatabaseMigrator:
    """Handles database migrations for SQLite databases"""

    def __init__(self, db_path: str, migrations_dir: str = None):
        self.db_path = db_path

        package_migrations_dir = Path(__file__).resolve().parent / "migrations"
        if migrations_dir is not None:
            chosen_dir = Path(migrations_dir)
            chosen_dir.mkdir(parents=True, exist_ok=True)
        elif package_migrations_dir.exists():
            chosen_dir = package_migrations_dir
        else:
            fallback_dir = Path(db_path).resolve().parent / "migrations"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            chosen_dir = fallback_dir

        self.migrations_dir = str(chosen_dir)

        # Backup directory
        self.backup_dir = os.path.join(
            os.path.dirname(db_path), "backups"
        )
        os.makedirs(self.backup_dir, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def initialize_migration_table(self):
        """Create migration tracking table if it doesn't exist"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMP NOT NULL,
                    execution_time REAL NOT NULL,
                    success BOOLEAN NOT NULL DEFAULT 1,
                    error_message TEXT
                )
            """)
            conn.commit()
            logger.info("Migration tracking table initialized")

    def get_current_version(self) -> int:
        """Get current schema version from database"""
        self.initialize_migration_table()

        with self._get_connection() as conn:
            # Try new migration table first
            result = conn.execute("""
                SELECT MAX(version) as version
                FROM schema_migrations
                WHERE success = 1
            """).fetchone()

            if result and result["version"] is not None:
                return result["version"]

            # Fall back to old schema_version table if exists
            try:
                result = conn.execute("""
                    SELECT version FROM schema_version LIMIT 1
                """).fetchone()
                if result:
                    return result["version"]
            except sqlite3.OperationalError:
                pass

            return 0

    def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """Get list of applied migrations"""
        self.initialize_migration_table()

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT version, name, checksum, applied_at, execution_time
                FROM schema_migrations
                WHERE success = 1
                ORDER BY version
            """)

            return [dict(row) for row in cursor]

    def load_migrations(self) -> List[Migration]:
        """Load all migrations from the migrations directory"""
        migrations = []

        logger.info(f"Loading migrations from directory: {self.migrations_dir}")

        # Check if directory exists
        if not os.path.exists(self.migrations_dir):
            logger.warning(f"Migrations directory does not exist: {self.migrations_dir}")
            return migrations

        seen_versions: Dict[int, Path] = {}

        for filepath in sorted(Path(self.migrations_dir).glob("*")):
            suffix = filepath.suffix.lower()
            try:
                if suffix == ".json":
                    migration = Migration.from_file(filepath)
                elif suffix == ".sql":
                    migration = self._load_sql_migration(filepath)
                else:
                    continue
            except Exception as e:
                logger.error(f"Failed to load migration from {filepath}: {e}")
                continue

            if not migration:
                continue

            previous = seen_versions.get(migration.version)
            if previous:
                logger.warning(
                    "Skipping migration {} from {}; version {} already provided by {}",
                    migration.name,
                    filepath.name,
                    migration.version,
                    previous.name,
                )
                continue

            migrations.append(migration)
            seen_versions[migration.version] = filepath
            logger.debug(f"Loaded migration: {migration.name} (v{migration.version})")

        # Sort by version to ensure deterministic execution order
        migrations.sort(key=lambda m: m.version)
        return migrations

    @staticmethod
    def _strip_sql_comments(sql: str) -> str:
        lines = []
        for line in sql.splitlines():
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_version_from_sql(filepath: Path, sql: str) -> int:
        match = re.match(r"(\d+)", filepath.stem)
        if match:
            return int(match.group(1))

        for line in sql.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("-- version:"):
                try:
                    return int(stripped.split(":", 1)[1].strip())
                except ValueError:
                    break

        raise ValueError(f"Unable to determine migration version for {filepath.name}")

    @staticmethod
    def _extract_name_from_sql(filepath: Path) -> str:
        match = re.match(r"\d+_(.+)", filepath.stem)
        if match:
            return match.group(1)
        return filepath.stem

    @staticmethod
    def _extract_description_from_sql(sql: str) -> str:
        for line in sql.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("-- description:"):
                return stripped.split(":", 1)[1].strip()
        return ""

    def _load_sql_migration(self, filepath: Path) -> Optional[Migration]:
        try:
            sql_text = filepath.read_text()
        except OSError as exc:
            logger.error(f"Unable to read migration file {filepath}: {exc}")
            return None

        executable_sql = self._strip_sql_comments(sql_text)
        if not executable_sql:
            logger.debug(f"Skipping SQL migration with no executable statements: {filepath.name}")
            return None

        version = self._extract_version_from_sql(filepath, sql_text)
        name = self._extract_name_from_sql(filepath)
        description = self._extract_description_from_sql(sql_text)

        return Migration(
            version=version,
            name=name,
            up_sql=sql_text,
            down_sql=None,
            description=description,
        )

    def create_backup(self, description: str = "") -> str:
        """Create a backup of the database before migration"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        version = self.get_current_version()

        backup_filename = f"backup_v{version}_{timestamp}.db"
        if description:
            safe_desc = "".join(c for c in description if c.isalnum() or c in "-_")[:50]
            backup_filename = f"backup_v{version}_{timestamp}_{safe_desc}.db"

        backup_path = os.path.join(self.backup_dir, backup_filename)

        # Create a consistent snapshot even when WAL journaling is enabled.
        try:
            with sqlite3.connect(self.db_path) as source, sqlite3.connect(backup_path) as target:
                try:
                    source.execute("PRAGMA wal_checkpoint(PASSIVE)")
                except sqlite3.OperationalError:
                    # Likely not in WAL mode; ignore.
                    pass
                source.backup(target)
        except sqlite3.Error as exc:
            raise MigrationError(f"Failed to create SQLite backup: {exc}") from exc

        # Create backup metadata
        metadata = {
            "original_path": self.db_path,
            "backup_path": backup_path,
            "timestamp": timestamp,
            "version": version,
            "description": description,
            "size": os.path.getsize(backup_path)
        }

        metadata_path = backup_path + ".json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Created backup: {backup_filename}")
        return backup_path

    def execute_migration(self, migration: Migration, direction: str = "up") -> float:
        """Execute a single migration"""
        sql = migration.up_sql if direction == "up" else migration.down_sql
        if direction == "down":
            if sql is None or not str(sql).strip():
                raise MigrationError(
                    f"Migration {migration.name} (v{migration.version}) does not define down_sql; downgrade is not supported."
                )
        assert sql is not None  # For type checkers
        start_time = datetime.now(timezone.utc)

        with self._get_connection() as conn:
            try:
                # Execute migration SQL
                if ";" in sql:
                    # Multiple statements
                    conn.executescript(sql)
                else:
                    # Single statement
                    conn.execute(sql)

                conn.commit()

                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

                # Record successful migration
                if direction == "up":
                    conn.execute("""
                        INSERT INTO schema_migrations
                        (version, name, checksum, applied_at, execution_time, success)
                        VALUES (?, ?, ?, ?, ?, 1)
                    """, (
                        migration.version,
                        migration.name,
                        migration.checksum,
                        datetime.now(timezone.utc),
                        execution_time
                    ))
                else:
                    # Remove migration record on rollback
                    conn.execute("""
                        DELETE FROM schema_migrations WHERE version = ?
                    """, (migration.version,))

                conn.commit()

                # Update schema_version table if it exists (for compatibility with MediaDB)
                try:
                    if direction == "up":
                        conn.execute("UPDATE schema_version SET version = ? WHERE 1=1", (migration.version,))
                    else:
                        # On downgrade, set to previous version
                        conn.execute("UPDATE schema_version SET version = ? WHERE 1=1", (migration.version - 1,))
                    conn.commit()
                except sqlite3.OperationalError:
                    # Table doesn't exist, that's fine
                    pass

                logger.info(
                    f"Executed migration {migration.name} ({direction}) "
                    f"in {execution_time:.2f}s"
                )

                return execution_time

            except Exception as e:
                conn.rollback()

                # Record failed migration
                if direction == "up":
                    try:
                        conn.execute("""
                            INSERT INTO schema_migrations
                            (version, name, checksum, applied_at, execution_time,
                             success, error_message)
                            VALUES (?, ?, ?, ?, ?, 0, ?)
                        """, (
                            migration.version,
                            migration.name,
                            migration.checksum,
                            datetime.now(timezone.utc),
                            (datetime.now(timezone.utc) - start_time).total_seconds(),
                            str(e)
                        ))
                        conn.commit()
                    except Exception as log_err:
                        logger.debug(f"Failed to log migration failure: migration={migration.name}, error={log_err}")

                raise MigrationError(
                    f"Migration {migration.name} ({direction}) failed: {e}"
                )

    def migrate_to_version(
        self,
        target_version: Optional[int] = None,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """Migrate database to target version"""
        current_version = self.get_current_version()
        migrations = self.load_migrations()

        if target_version is None:
            # Migrate to latest
            target_version = migrations[-1].version if migrations else 0

        logger.info(
            f"Migrating from version {current_version} to {target_version}"
        )

        # Determine migrations to apply
        if target_version > current_version:
            # Upgrade
            to_apply = [
                m for m in migrations
                if current_version < m.version <= target_version
            ]
            direction = "up"
        elif target_version < current_version:
            # Downgrade
            to_apply = [
                m for m in reversed(migrations)
                if target_version < m.version <= current_version
            ]
            direction = "down"
        else:
            # Already at target version
            return {
                "status": "no_change",
                "current_version": current_version,
                "target_version": target_version,
                "migrations_applied": []
            }

        if not to_apply:
            return {
                "status": "no_migrations",
                "current_version": current_version,
                "target_version": target_version,
                "migrations_applied": []
            }

        # Create backup before migration
        backup_path = None
        if create_backup:
            backup_path = self.create_backup(
                f"before_migration_to_v{target_version}"
            )

        # Apply migrations
        applied = []
        total_time = 0.0

        try:
            for migration in to_apply:
                execution_time = self.execute_migration(migration, direction)
                applied.append({
                    "version": migration.version,
                    "name": migration.name,
                    "direction": direction,
                    "execution_time": execution_time
                })
                total_time += execution_time

            new_version = self.get_current_version()

            return {
                "status": "success",
                "previous_version": current_version,
                "current_version": new_version,
                "target_version": target_version,
                "migrations_applied": applied,
                "total_execution_time": total_time,
                "backup_path": backup_path
            }

        except Exception as e:
            logger.error(f"Migration failed: {e}")

            # Attempt rollback to original version
            if backup_path and create_backup:
                logger.info(f"Migration failed. Backup available at: {backup_path}")

            raise MigrationError(f"Migration failed: {e}")

    def rollback_to_backup(self, backup_path: str):
        """Restore database from backup"""
        if not os.path.exists(backup_path):
            raise MigrationError(f"Backup not found: {backup_path}")

        # Create a safety backup of current state
        safety_backup = self.create_backup("before_rollback")

        try:
            # Replace current database with backup
            shutil.copy2(backup_path, self.db_path)
            for suffix in ("-wal", "-shm"):
                backup_sidecar = f"{backup_path}{suffix}"
                target_sidecar = f"{self.db_path}{suffix}"
                if os.path.exists(backup_sidecar):
                    shutil.copy2(backup_sidecar, target_sidecar)
                    logger.info(f"Restored journal file: {target_sidecar}")
                elif os.path.exists(target_sidecar):
                    os.remove(target_sidecar)
                    logger.info(f"Removed stale journal file: {target_sidecar}")
            logger.info(f"Rolled back to backup: {backup_path}")

            return {
                "status": "success",
                "restored_from": backup_path,
                "safety_backup": safety_backup
            }

        except Exception as e:
            raise MigrationError(f"Rollback failed: {e}")

    def verify_migrations(self) -> List[Dict[str, Any]]:
        """Verify integrity of applied migrations"""
        issues = []
        applied = self.get_applied_migrations()
        available = {m.version: m for m in self.load_migrations()}

        for migration_record in applied:
            version = migration_record["version"]

            if version not in available:
                issues.append({
                    "version": version,
                    "issue": "migration_file_missing",
                    "message": f"Migration file for version {version} not found"
                })
                continue

            migration = available[version]
            if migration.checksum != migration_record["checksum"]:
                issues.append({
                    "version": version,
                    "issue": "checksum_mismatch",
                    "message": f"Checksum mismatch for migration {version}",
                    "expected": migration.checksum,
                    "actual": migration_record["checksum"]
                })

        return issues


# Convenience functions
def get_migrator(db_path: str) -> DatabaseMigrator:
    """Get a configured migrator instance"""
    return DatabaseMigrator(db_path)


def migrate_database(
    db_path: str,
    target_version: Optional[int] = None,
    create_backup: bool = True
) -> Dict[str, Any]:
    """Migrate database to target version"""
    migrator = get_migrator(db_path)
    return migrator.migrate_to_version(target_version, create_backup)


__all__ = [
    'Migration',
    'MigrationError',
    'DatabaseMigrator',
    'get_migrator',
    'migrate_database'
]
