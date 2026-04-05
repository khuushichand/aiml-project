"""Database migration for synthetic evaluation draft persistence."""

from __future__ import annotations

import sqlite3

from loguru import logger


def migrate_to_synthetic_eval_workflow(db_path: str) -> bool:
    """Create the synthetic eval draft, review, and promotion tables."""

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            def _table_columns(table_name: str) -> set[str]:
                cursor.execute(f"PRAGMA table_info('{table_name}')")
                return {row[1] for row in cursor.fetchall()}

            def _add_column_if_missing(table_name: str, column_name: str, column_sql: str) -> None:
                if column_name not in _table_columns(table_name):
                    cursor.execute(column_sql)

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS synthetic_eval_draft_samples (
                    sample_id TEXT PRIMARY KEY,
                    recipe_kind TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    review_state TEXT NOT NULL DEFAULT 'draft',
                    sample_payload_json TEXT NOT NULL,
                    sample_metadata_json TEXT,
                    source_kind TEXT,
                    created_by TEXT,
                    review_summary_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS synthetic_eval_review_actions (
                    action_id TEXT PRIMARY KEY,
                    sample_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reviewer_id TEXT,
                    notes TEXT,
                    action_payload_json TEXT,
                    resulting_review_state TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sample_id) REFERENCES synthetic_eval_draft_samples(sample_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS synthetic_eval_promotions (
                    promotion_id TEXT PRIMARY KEY,
                    sample_id TEXT NOT NULL,
                    dataset_id TEXT,
                    dataset_snapshot_ref TEXT,
                    promoted_by TEXT,
                    promotion_reason TEXT,
                    promotion_metadata_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sample_id) REFERENCES synthetic_eval_draft_samples(sample_id)
                )
                """
            )

            for index_sql in [
                "CREATE INDEX IF NOT EXISTS idx_synth_eval_samples_recipe ON synthetic_eval_draft_samples(recipe_kind)",
                "CREATE INDEX IF NOT EXISTS idx_synth_eval_samples_provenance ON synthetic_eval_draft_samples(provenance)",
                "CREATE INDEX IF NOT EXISTS idx_synth_eval_samples_review_state ON synthetic_eval_draft_samples(review_state)",
                "CREATE INDEX IF NOT EXISTS idx_synth_eval_samples_created_at ON synthetic_eval_draft_samples(created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_synth_eval_actions_sample_created ON synthetic_eval_review_actions(sample_id, created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_synth_eval_promotions_sample_created ON synthetic_eval_promotions(sample_id, created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_synth_eval_promotions_dataset ON synthetic_eval_promotions(dataset_id)",
            ]:
                cursor.execute(index_sql)

            _add_column_if_missing("synthetic_eval_draft_samples", "sample_metadata_json", "ALTER TABLE synthetic_eval_draft_samples ADD COLUMN sample_metadata_json TEXT")
            _add_column_if_missing("synthetic_eval_draft_samples", "source_kind", "ALTER TABLE synthetic_eval_draft_samples ADD COLUMN source_kind TEXT")
            _add_column_if_missing("synthetic_eval_draft_samples", "created_by", "ALTER TABLE synthetic_eval_draft_samples ADD COLUMN created_by TEXT")
            _add_column_if_missing("synthetic_eval_draft_samples", "review_summary_json", "ALTER TABLE synthetic_eval_draft_samples ADD COLUMN review_summary_json TEXT")
            _add_column_if_missing("synthetic_eval_draft_samples", "updated_at", "ALTER TABLE synthetic_eval_draft_samples ADD COLUMN updated_at TEXT")

            _add_column_if_missing("synthetic_eval_review_actions", "reviewer_id", "ALTER TABLE synthetic_eval_review_actions ADD COLUMN reviewer_id TEXT")
            _add_column_if_missing("synthetic_eval_review_actions", "notes", "ALTER TABLE synthetic_eval_review_actions ADD COLUMN notes TEXT")
            _add_column_if_missing("synthetic_eval_review_actions", "action_payload_json", "ALTER TABLE synthetic_eval_review_actions ADD COLUMN action_payload_json TEXT")
            _add_column_if_missing("synthetic_eval_review_actions", "resulting_review_state", "ALTER TABLE synthetic_eval_review_actions ADD COLUMN resulting_review_state TEXT")
            _add_column_if_missing("synthetic_eval_review_actions", "created_at", "ALTER TABLE synthetic_eval_review_actions ADD COLUMN created_at TEXT")

            _add_column_if_missing("synthetic_eval_promotions", "dataset_id", "ALTER TABLE synthetic_eval_promotions ADD COLUMN dataset_id TEXT")
            _add_column_if_missing("synthetic_eval_promotions", "dataset_snapshot_ref", "ALTER TABLE synthetic_eval_promotions ADD COLUMN dataset_snapshot_ref TEXT")
            _add_column_if_missing("synthetic_eval_promotions", "promoted_by", "ALTER TABLE synthetic_eval_promotions ADD COLUMN promoted_by TEXT")
            _add_column_if_missing("synthetic_eval_promotions", "promotion_reason", "ALTER TABLE synthetic_eval_promotions ADD COLUMN promotion_reason TEXT")
            _add_column_if_missing("synthetic_eval_promotions", "promotion_metadata_json", "ALTER TABLE synthetic_eval_promotions ADD COLUMN promotion_metadata_json TEXT")
            _add_column_if_missing("synthetic_eval_promotions", "created_at", "ALTER TABLE synthetic_eval_promotions ADD COLUMN created_at TEXT")

            conn.commit()
            logger.info("Applied synthetic eval workflow migration successfully")
            return True
    except Exception as exc:  # pragma: no cover - defensive migration wrapper
        logger.error("Failed to migrate synthetic eval workflow schema: {}", exc)
        return False
