from __future__ import annotations

from typing import Literal

SourceType = Literal["local_directory", "archive_snapshot"]
SinkType = Literal["media", "notes"]
SourcePolicy = Literal["canonical", "import_only"]

SOURCE_TYPES: frozenset[str] = frozenset({"local_directory", "archive_snapshot"})
SINK_TYPES: frozenset[str] = frozenset({"media", "notes"})
SOURCE_POLICIES: frozenset[str] = frozenset({"canonical", "import_only"})
