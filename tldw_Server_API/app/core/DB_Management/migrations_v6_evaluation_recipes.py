"""Database migration for the evaluation recipe framework."""

from __future__ import annotations

import contextlib
import sqlite3

from loguru import logger


def migrate_to_evaluation_recipes(db_path: str) -> bool:
    """Create the recipe-run tables used by the recipe framework."""

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_recipe_runs (
                    run_id TEXT PRIMARY KEY,
                    recipe_id TEXT NOT NULL,
                    recipe_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    review_state TEXT NOT NULL DEFAULT 'not_required',
                    dataset_snapshot_ref TEXT,
                    dataset_content_hash TEXT,
                    confidence_summary_json TEXT,
                    recommendation_slots_json TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_recipe_run_children (
                    parent_run_id TEXT NOT NULL,
                    child_run_id TEXT NOT NULL,
                    child_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (parent_run_id, child_run_id),
                    FOREIGN KEY (parent_run_id) REFERENCES evaluation_recipe_runs(run_id)
                )
                """
            )

            for index_sql in [
                "CREATE INDEX IF NOT EXISTS idx_eval_recipe_runs_recipe_id ON evaluation_recipe_runs(recipe_id)",
                "CREATE INDEX IF NOT EXISTS idx_eval_recipe_runs_status ON evaluation_recipe_runs(status)",
                "CREATE INDEX IF NOT EXISTS idx_eval_recipe_runs_created_at ON evaluation_recipe_runs(created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_eval_recipe_children_parent ON evaluation_recipe_run_children(parent_run_id)",
                "CREATE INDEX IF NOT EXISTS idx_eval_recipe_children_child ON evaluation_recipe_run_children(child_run_id)",
            ]:
                cursor.execute(index_sql)

            cursor.execute("PRAGMA table_info('evaluation_recipe_runs')")
            columns = {row[1] for row in cursor.fetchall()}
            for column_name, column_sql in [
                ("dataset_snapshot_ref", "ALTER TABLE evaluation_recipe_runs ADD COLUMN dataset_snapshot_ref TEXT"),
                ("dataset_content_hash", "ALTER TABLE evaluation_recipe_runs ADD COLUMN dataset_content_hash TEXT"),
                ("confidence_summary_json", "ALTER TABLE evaluation_recipe_runs ADD COLUMN confidence_summary_json TEXT"),
                ("recommendation_slots_json", "ALTER TABLE evaluation_recipe_runs ADD COLUMN recommendation_slots_json TEXT"),
                ("metadata_json", "ALTER TABLE evaluation_recipe_runs ADD COLUMN metadata_json TEXT"),
                ("review_state", "ALTER TABLE evaluation_recipe_runs ADD COLUMN review_state TEXT NOT NULL DEFAULT 'not_required'"),
                ("updated_at", "ALTER TABLE evaluation_recipe_runs ADD COLUMN updated_at TEXT"),
            ]:
                if column_name not in columns:
                    with contextlib.suppress(sqlite3.Error):
                        cursor.execute(column_sql)

            with contextlib.suppress(sqlite3.Error):
                cursor.execute(
                    "UPDATE evaluation_recipe_runs SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
                )

            conn.commit()
            logger.info("Applied evaluation recipe schema migration")
            return True
    except Exception as exc:  # pragma: no cover - defensive migration wrapper
        logger.error("Failed to migrate evaluation recipe schema: {}", exc)
        return False
