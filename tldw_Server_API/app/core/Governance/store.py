"""Persistence primitives for governance policies, gaps, and validation traces."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

import aiosqlite


@dataclass(frozen=True)
class GapRecord:
    """Normalized governance gap record."""

    id: int
    question: str
    question_fingerprint: str
    category: str
    status: str
    org_id: Optional[int]
    team_id: Optional[int]
    persona_id: Optional[str]
    workspace_id: Optional[str]
    resolution_mode: Optional[str]
    resolution_text: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "GapRecord":
        return cls(
            id=int(row["id"]),
            question=str(row["question"]),
            question_fingerprint=str(row["question_fingerprint"]),
            category=str(row["category"]),
            status=str(row["status"]),
            org_id=row["org_id"],
            team_id=row["team_id"],
            persona_id=row["persona_id"],
            workspace_id=row["workspace_id"],
            resolution_mode=row["resolution_mode"],
            resolution_text=row["resolution_text"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )


class GovernanceStore:
    """SQLite-backed governance store focused on deterministic safety semantics."""

    def __init__(self, sqlite_path: str) -> None:
        self.sqlite_path = sqlite_path

    def _connect(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.sqlite_path)

    async def ensure_schema(self) -> None:
        """Ensure governance storage tables exist."""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS governance_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER,
                    team_id INTEGER,
                    persona_id TEXT,
                    workspace_id TEXT,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    body_markdown TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    priority INTEGER NOT NULL DEFAULT 0,
                    effective_from TEXT,
                    expires_at TEXT,
                    created_by TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS governance_gaps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER,
                    team_id INTEGER,
                    persona_id TEXT,
                    workspace_id TEXT,
                    question TEXT NOT NULL,
                    question_fingerprint TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    resolution_mode TEXT,
                    resolution_text TEXT,
                    owner_user_id INTEGER,
                    review_due_at TEXT,
                    resolved_by TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE UNIQUE INDEX IF NOT EXISTS uq_governance_gaps_open_dedupe
                ON governance_gaps (
                    question_fingerprint,
                    category,
                    COALESCE(org_id, -1),
                    COALESCE(team_id, -1),
                    COALESCE(persona_id, ''),
                    COALESCE(workspace_id, '')
                )
                WHERE status = 'open';
                """
            )
            await db.commit()

    async def table_exists(self, table_name: str) -> bool:
        """Return True when a SQLite table exists."""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
                (table_name,),
            )
            row = await cursor.fetchone()
            return bool(row)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(str(text or "").strip().split())

    @classmethod
    def _question_fingerprint(cls, question: str) -> str:
        normalized = cls._normalize_text(question).lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def upsert_open_gap(
        self,
        *,
        question: str,
        category: str,
        org_id: int | None = None,
        team_id: int | None = None,
        persona_id: str | None = None,
        workspace_id: str | None = None,
        resolution_mode: str | None = None,
    ) -> GapRecord:
        """Create or return an existing open gap for the same normalized question/scope."""
        normalized_question = self._normalize_text(question)
        normalized_category = self._normalize_text(category).lower()
        if not normalized_question:
            raise ValueError("question is required")
        if not normalized_category:
            raise ValueError("category is required")

        fingerprint = self._question_fingerprint(normalized_question)
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute(
                    """
                    INSERT INTO governance_gaps (
                        org_id, team_id, persona_id, workspace_id,
                        question, question_fingerprint, category, status, resolution_mode
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
                    """,
                    (
                        org_id,
                        team_id,
                        persona_id,
                        workspace_id,
                        normalized_question,
                        fingerprint,
                        normalized_category,
                        resolution_mode,
                    ),
                )
                await db.commit()
            except aiosqlite.IntegrityError:
                # Existing open gap for same fingerprint/scope. Return that row.
                pass

            cursor = await db.execute(
                """
                SELECT id, org_id, team_id, persona_id, workspace_id,
                       question, question_fingerprint, category, status,
                       resolution_mode, resolution_text, created_at, updated_at
                FROM governance_gaps
                WHERE status = 'open'
                  AND question_fingerprint = ?
                  AND category = ?
                  AND COALESCE(org_id, -1) = COALESCE(?, -1)
                  AND COALESCE(team_id, -1) = COALESCE(?, -1)
                  AND COALESCE(persona_id, '') = COALESCE(?, '')
                  AND COALESCE(workspace_id, '') = COALESCE(?, '')
                ORDER BY id ASC
                LIMIT 1
                """,
                (
                    fingerprint,
                    normalized_category,
                    org_id,
                    team_id,
                    persona_id,
                    workspace_id,
                ),
            )
            row = await cursor.fetchone()
            if row is None:
                raise RuntimeError("failed to load governance gap after upsert")
            return GapRecord.from_row(row)
