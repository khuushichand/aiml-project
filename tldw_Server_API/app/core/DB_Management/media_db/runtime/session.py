"""Request-scoped session helpers for the Media DB package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


DatabaseFactory = Callable[..., Any]


def _load_default_media_database_factory() -> DatabaseFactory:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime.factory import (
        _load_media_database_cls,
    )

    return _load_media_database_cls()


@dataclass(slots=True)
class MediaDbSession:
    db_path: str
    client_id: str
    database: Any
    org_id: int | None = None
    team_id: int | None = None

    def __getattr__(self, item: str) -> Any:
        return getattr(self.database, item)

    def release_context_connection(self) -> None:
        release = getattr(self.database, "release_context_connection", None)
        if callable(release):
            release()


@dataclass(slots=True)
class MediaDbFactory:
    db_path: str
    client_id: str
    backend: Any = None
    database_factory: DatabaseFactory | None = None

    @classmethod
    def for_sqlite_path(cls, db_path: str, client_id: str) -> "MediaDbFactory":
        return cls(db_path=db_path, client_id=client_id)

    def for_request(
        self,
        *,
        org_id: int | None = None,
        team_id: int | None = None,
    ) -> MediaDbSession:
        database_factory = self.database_factory
        if database_factory is None:
            database_factory = _load_default_media_database_factory()

        if self.backend is not None:
            database = database_factory(
                db_path=self.db_path,
                client_id=self.client_id,
                backend=self.backend,
            )
        else:
            database = database_factory(
                db_path=self.db_path,
                client_id=self.client_id,
            )

        if hasattr(database, "default_org_id"):
            database.default_org_id = org_id
        if hasattr(database, "default_team_id"):
            database.default_team_id = team_id

        return MediaDbSession(
            db_path=self.db_path,
            client_id=self.client_id,
            database=database,
            org_id=org_id,
            team_id=team_id,
        )
