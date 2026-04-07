"""PostgreSQL TTS-history migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol


class PostgresTTSHistoryBody(Protocol):
    """Protocol for DB objects that can ensure PostgreSQL TTS-history state."""

    def _ensure_postgres_tts_history(self, conn: Any) -> None: ...


def run_postgres_migrate_to_v20(db: PostgresTTSHistoryBody, conn: Any) -> None:
    """Run the PostgreSQL v20 TTS-history migration body."""

    db._ensure_postgres_tts_history(conn)


__all__ = [
    "PostgresTTSHistoryBody",
    "run_postgres_migrate_to_v20",
]
