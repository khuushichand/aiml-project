Database Migrations Overview

This project maintains multiple logical databases with distinct migration registries:

- Content databases (Media/ChaCha/etc.)
  - Registry: `schema_version` (single-row integer) and `schema_migrations` (for legacy tracking via the DatabaseMigrator).
  - Location: Managed primarily within `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py` and the `db_migration.py` helper.
  - Backends: SQLite (default) and PostgreSQL (optional). PostgreSQL migrations are applied inline via helper methods in `Media_DB_v2`.

- Evaluations/Audit databases
  - Registry: `schema_version` and `migrations` tables for applied steps and verification.
  - Location: `migrations_v5_unified_evaluations.py` and `migrations_v6_audit_logging.py` maintain their own registries to reflect the independent lifecycle of these stores.

Why two registries?

- Content schema updates are tightly coupled to runtime application boot (for both SQLite and PostgreSQL) and often need inline verification (FTS, RLS policies). The single version integer plus inline checks keep the boot path fast and predictable.
- Evaluations/Audit introduce separate, self-contained features and may be operated as distinct databases. Their modules maintain a `migrations` history to aid exporting, auditing and verification tasks without coupling to content store versioning.

Guidance

- When changing Media/ChaCha schema: update `Media_DB_v2._CURRENT_SCHEMA_VERSION` and add inline migration helpers or SQLite migration SQL files (under `DB_Management/migrations/`).
- When changing Evaluations/Audit schema: update the appropriate migration module and record the step in the module’s registry tables.
- Keep tests aligned with the registry logic: content tests should validate `schema_version` and FTS/RLS; evaluation tests should validate both `schema_version` and `migrations` integrity.
