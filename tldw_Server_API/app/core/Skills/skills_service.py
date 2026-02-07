# app/core/Skills/skills_service.py
#
# Service for managing skills (CRUD operations and file management)
#
"""
Skills Service
==============

Manages skills stored as SKILL.md files in user directories:
- user_databases/{user_id}/skills/{skill_name}/SKILL.md

Provides:
- CRUD operations for skills
- Import/export functionality
- Context payload generation for LLM injection
"""

import asyncio
import contextlib
import shutil
import time
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)
from tldw_Server_API.app.core.Skills.exceptions import (
    SkillConflictError,
    SkillNotFoundError,
    SkillsError,
    SkillStorageError,
    SkillValidationError,
)
from tldw_Server_API.app.core.Skills.skill_parser import SkillFrontmatter, SkillParser


class SkillMetadata:
    """Metadata for a stored skill."""

    def __init__(
        self,
        id: str,
        name: str,
        description: Optional[str] = None,
        argument_hint: Optional[str] = None,
        disable_model_invocation: bool = False,
        user_invocable: bool = True,
        allowed_tools: Optional[list[str]] = None,
        model: Optional[str] = None,
        context: str = "inline",
        directory_path: str = "",
        content_hash: Optional[str] = None,
        created_at: Optional[datetime] = None,
        last_modified: Optional[datetime] = None,
        version: int = 1,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.argument_hint = argument_hint
        self.disable_model_invocation = disable_model_invocation
        self.user_invocable = user_invocable
        self.allowed_tools = allowed_tools or []
        self.model = model
        self.context = context
        self.directory_path = directory_path
        self.content_hash = content_hash
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_modified = last_modified or datetime.now(timezone.utc)
        self.version = version

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "argument_hint": self.argument_hint,
            "disable_model_invocation": self.disable_model_invocation,
            "user_invocable": self.user_invocable,
            "allowed_tools": self.allowed_tools,
            "model": self.model,
            "context": self.context,
            "directory_path": self.directory_path,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillMetadata":
        created_at = data.get("created_at")
        last_modified = data.get("last_modified")

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(last_modified, str):
            last_modified = datetime.fromisoformat(last_modified)

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            argument_hint=data.get("argument_hint"),
            disable_model_invocation=data.get("disable_model_invocation", False),
            user_invocable=data.get("user_invocable", True),
            allowed_tools=data.get("allowed_tools"),
            model=data.get("model"),
            context=data.get("context", "inline"),
            directory_path=data.get("directory_path", ""),
            content_hash=data.get("content_hash"),
            created_at=created_at,
            last_modified=last_modified,
            version=data.get("version", 1),
        )


class SkillsService:
    """Central service for skill management."""

    def __init__(
        self,
        user_id: int,
        base_path: Path,
        db: CharactersRAGDB | None = None,
        sync_interval: float = 5.0,
    ):
        """
        Initialize the SkillsService.

        Args:
            user_id: The user ID for skill isolation
            base_path: Base path for user databases (e.g., Databases/user_databases/{user_id}/)
            db: CharactersRAGDB instance for skill registry persistence
            sync_interval: Minimum seconds between filesystem syncs for read operations
        """
        self.user_id = user_id
        self.base_path = Path(base_path)
        self.skills_dir = self.base_path / "skills"
        self.db = db
        self._parser = SkillParser()
        self._sync_interval = sync_interval
        self._last_sync_time: float = 0.0
        self._ensure_skills_directory()
        self._ensure_registry_ready()

    def _ensure_skills_directory(self) -> None:
        """Ensure the skills directory exists."""
        try:
            self.skills_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise SkillStorageError(
                f"Failed to create skills directory: {e}",
                path=str(self.skills_dir),
            ) from e

    def _ensure_registry_ready(self) -> None:
        """Ensure the skill registry table is available."""
        if self.db is None:
            raise SkillsError("SkillsService requires a database instance for registry operations.")
        try:
            self.db._ensure_skill_registry_table()
        except CharactersRAGDBError as e:
            raise SkillsError(f"Failed to ensure skill registry table: {e}") from e

    def _get_db(self) -> CharactersRAGDB:
        if self.db is None:
            raise SkillsError("SkillsService requires a database instance for registry operations.")
        return self.db

    def _get_skill_dir(self, name: str) -> Path:
        """Get the directory path for a skill."""
        return self.skills_dir / name

    def _parse_skill_file(self, skill_dir: Path) -> Optional[Any]:
        """Parse SKILL.md content without loading supporting files."""
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return None
        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to read SKILL.md for {skill_dir.name}: {e}")
            return None
        try:
            return self._parser.parse_content(content, default_name=skill_dir.name)
        except Exception as e:
            logger.warning(f"Failed to parse SKILL.md for {skill_dir.name}: {e}")
            return None

    def _metadata_from_row(self, row: dict[str, Any]) -> SkillMetadata:
        created_at = row.get("created_at")
        last_modified = row.get("last_modified")
        return SkillMetadata(
            id=row.get("uuid") or row.get("id"),
            name=row.get("name") or "",
            description=row.get("description"),
            argument_hint=row.get("argument_hint"),
            disable_model_invocation=bool(row.get("disable_model_invocation", False)),
            user_invocable=bool(row.get("user_invocable", True)),
            allowed_tools=row.get("allowed_tools"),
            model=row.get("model"),
            context=row.get("context", "inline"),
            directory_path=row.get("directory_path", ""),
            content_hash=row.get("file_hash"),
            created_at=created_at if isinstance(created_at, datetime) else datetime.now(timezone.utc),
            last_modified=last_modified if isinstance(last_modified, datetime) else datetime.now(timezone.utc),
            version=int(row.get("version") or 1),
        )

    def _sync_registry(self) -> None:
        """Synchronize skill_registry with filesystem contents."""
        db = self._get_db()
        try:
            registry_rows = db.list_skill_registry(
                include_hidden=True,
                include_deleted=True,
                limit=10000,
                offset=0,
            )
        except CharactersRAGDBError as e:
            logger.error(f"Failed to read skill registry: {e}")
            raise SkillsError(f"Failed to read skill registry: {e}") from e

        registry_by_name = {row.get("name"): row for row in registry_rows if row and row.get("name")}

        disk_names: set[str] = set()
        if self.skills_dir.exists():
            for item in self.skills_dir.iterdir():
                if not item.is_dir():
                    continue
                if not (item / "SKILL.md").exists():
                    continue

                disk_names.add(item.name)
                parsed = self._parse_skill_file(item)
                if not parsed:
                    continue

                existing = registry_by_name.get(item.name)
                if existing is None:
                    try:
                        db.insert_skill_registry(
                            {
                                "name": item.name,
                                "description": parsed.frontmatter.description,
                                "argument_hint": parsed.frontmatter.argument_hint,
                                "disable_model_invocation": parsed.frontmatter.disable_model_invocation,
                                "user_invocable": parsed.frontmatter.user_invocable,
                                "allowed_tools": parsed.frontmatter.allowed_tools,
                                "model": parsed.frontmatter.model,
                                "context": parsed.frontmatter.context,
                                "directory_path": str(item),
                                "file_hash": parsed.content_hash,
                            }
                        )
                        logger.info(f"Indexed new skill '{item.name}' from disk")
                    except ConflictError:
                        logger.warning(f"Skill '{item.name}' already exists while syncing; skipping insert")
                    except CharactersRAGDBError as e:
                        logger.warning(f"Failed to insert skill '{item.name}' into registry: {e}")
                    continue

                if existing.get("deleted"):
                    update_data = {
                        "description": parsed.frontmatter.description,
                        "argument_hint": parsed.frontmatter.argument_hint,
                        "disable_model_invocation": parsed.frontmatter.disable_model_invocation,
                        "user_invocable": parsed.frontmatter.user_invocable,
                        "allowed_tools": parsed.frontmatter.allowed_tools,
                        "model": parsed.frontmatter.model,
                        "context": parsed.frontmatter.context,
                        "directory_path": str(item),
                        "file_hash": parsed.content_hash,
                        "deleted": 0,
                    }
                    try:
                        db.update_skill_registry(item.name, update_data, expected_version=existing.get("version", 1))
                        logger.info(f"Restored deleted skill '{item.name}' from disk")
                    except ConflictError as e:
                        logger.warning(f"Conflict restoring skill '{item.name}': {e}")
                    except CharactersRAGDBError as e:
                        logger.warning(f"Failed to restore skill '{item.name}': {e}")
                    continue

                if existing.get("file_hash") != parsed.content_hash:
                    update_data = {
                        "description": parsed.frontmatter.description,
                        "argument_hint": parsed.frontmatter.argument_hint,
                        "disable_model_invocation": parsed.frontmatter.disable_model_invocation,
                        "user_invocable": parsed.frontmatter.user_invocable,
                        "allowed_tools": parsed.frontmatter.allowed_tools,
                        "model": parsed.frontmatter.model,
                        "context": parsed.frontmatter.context,
                        "directory_path": str(item),
                        "file_hash": parsed.content_hash,
                    }
                    try:
                        db.update_skill_registry(item.name, update_data, expected_version=existing.get("version", 1))
                        logger.info(f"Updated skill registry for '{item.name}'")
                    except ConflictError as e:
                        logger.warning(f"Conflict updating skill '{item.name}': {e}")
                    except CharactersRAGDBError as e:
                        logger.warning(f"Failed to update skill '{item.name}': {e}")

        for name, row in registry_by_name.items():
            if name not in disk_names and not row.get("deleted"):
                try:
                    db.mark_skill_registry_deleted(name, expected_version=row.get("version", 1))
                    logger.info(f"Marked missing skill '{name}' as deleted")
                except ConflictError as e:
                    logger.warning(f"Conflict marking skill '{name}' deleted: {e}")
                except CharactersRAGDBError as e:
                    logger.warning(f"Failed to mark skill '{name}' deleted: {e}")

    async def list_skills(
        self,
        include_hidden: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SkillMetadata]:
        """
        List all skills for the user.

        Args:
            include_hidden: If True, include skills with user_invocable=False
            limit: Maximum number of skills to return
            offset: Offset for pagination

        Returns:
            List of skill metadata
        """
        self._sync_registry()
        db = self._get_db()
        rows = db.list_skill_registry(
            include_hidden=include_hidden,
            include_deleted=False,
            limit=limit,
            offset=offset,
        )
        return [self._metadata_from_row(row) for row in rows]

    async def get_skill(self, name: str) -> dict[str, Any]:
        """
        Get full skill content.

        Args:
            name: The skill name

        Returns:
            Full skill data including content

        Raises:
            SkillNotFoundError: If skill doesn't exist
        """
        name = name.strip().lower()
        self._sync_registry()
        db = self._get_db()

        row = db.get_skill_registry(name, include_deleted=False)
        if not row:
            raise SkillNotFoundError(name)

        metadata = self._metadata_from_row(row)
        skill_dir = self._get_skill_dir(name)
        if not skill_dir.exists():
            with contextlib.suppress(Exception):
                db.mark_skill_registry_deleted(name, expected_version=metadata.version)
            raise SkillNotFoundError(name, detail="Skill directory not found")

        try:
            parsed = self._parser.parse_directory(skill_dir)
        except Exception as e:
            raise SkillsError(f"Failed to parse skill: {e}") from e

        return {
            "id": metadata.id,
            "name": metadata.name,
            "description": parsed.frontmatter.description,
            "argument_hint": parsed.frontmatter.argument_hint,
            "disable_model_invocation": parsed.frontmatter.disable_model_invocation,
            "user_invocable": parsed.frontmatter.user_invocable,
            "allowed_tools": parsed.frontmatter.allowed_tools,
            "model": parsed.frontmatter.model,
            "context": parsed.frontmatter.context,
            "content": parsed.content,
            "supporting_files": parsed.supporting_files,
            "directory_path": str(skill_dir),
            "created_at": metadata.created_at,
            "last_modified": metadata.last_modified,
            "version": metadata.version,
        }

    async def create_skill(
        self,
        name: str,
        content: str,
        supporting_files: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Create a new skill.

        Args:
            name: The skill name (lowercase, hyphens only)
            content: Full SKILL.md content with optional frontmatter
            supporting_files: Additional files to include

        Returns:
            Created skill data

        Raises:
            SkillConflictError: If skill with this name already exists
            SkillValidationError: If content is invalid
        """
        name = name.strip().lower()
        self._sync_registry()
        db = self._get_db()

        existing = db.get_skill_registry(name, include_deleted=True)
        if existing and not existing.get("deleted"):
            raise SkillConflictError(f"Skill '{name}' already exists", skill_name=name)

        # Parse the content to validate
        try:
            parsed = self._parser.parse_content(content, default_name=name)
        except Exception as e:
            raise SkillValidationError(f"Invalid skill content: {e}") from e

        # Create skill directory
        skill_dir = self._get_skill_dir(name)
        try:
            skill_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise SkillConflictError(f"Skill directory '{name}' already exists", skill_name=name) from None
        except OSError as e:
            raise SkillStorageError(f"Failed to create skill directory: {e}", path=str(skill_dir)) from e

        # Write SKILL.md
        skill_file = skill_dir / "SKILL.md"
        try:
            skill_file.write_text(content, encoding="utf-8")
        except OSError as e:
            shutil.rmtree(skill_dir, ignore_errors=True)
            raise SkillStorageError(f"Failed to write SKILL.md: {e}", path=str(skill_file)) from e

        # Write supporting files
        if supporting_files:
            for filename, file_content in supporting_files.items():
                if file_content is None:
                    continue
                try:
                    (skill_dir / filename).write_text(file_content, encoding="utf-8")
                except OSError as e:
                    logger.warning(f"Failed to write supporting file {filename}: {e}")

        registry_payload = {
            "name": name,
            "description": parsed.frontmatter.description,
            "argument_hint": parsed.frontmatter.argument_hint,
            "disable_model_invocation": parsed.frontmatter.disable_model_invocation,
            "user_invocable": parsed.frontmatter.user_invocable,
            "allowed_tools": parsed.frontmatter.allowed_tools,
            "model": parsed.frontmatter.model,
            "context": parsed.frontmatter.context,
            "directory_path": str(skill_dir),
            "file_hash": parsed.content_hash,
        }

        try:
            if existing and existing.get("deleted"):
                db.update_skill_registry(name, {**registry_payload, "deleted": 0}, expected_version=existing.get("version", 1))
            else:
                db.insert_skill_registry(registry_payload)
        except ConflictError as e:
            shutil.rmtree(skill_dir, ignore_errors=True)
            raise SkillConflictError(str(e), skill_name=name) from e
        except (CharactersRAGDBError, InputError) as e:
            shutil.rmtree(skill_dir, ignore_errors=True)
            raise SkillsError(f"Failed to record skill '{name}' in registry: {e}") from e

        logger.info(f"Created skill '{name}' for user {self.user_id}")

        return await self.get_skill(name)

    async def update_skill(
        self,
        name: str,
        content: Optional[str] = None,
        supporting_files: Optional[dict[str, Optional[str]]] = None,
        expected_version: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Update an existing skill.

        Args:
            name: The skill name
            content: New SKILL.md content (optional)
            supporting_files: Files to add/update/remove (set value to None to remove)
            expected_version: Version for optimistic locking

        Returns:
            Updated skill data

        Raises:
            SkillNotFoundError: If skill doesn't exist
            SkillConflictError: If version mismatch
        """
        name = name.strip().lower()
        self._sync_registry()
        db = self._get_db()

        row = db.get_skill_registry(name, include_deleted=False)
        if not row:
            raise SkillNotFoundError(name)

        current_version = int(row.get("version") or 1)
        if expected_version is not None and current_version != expected_version:
            raise SkillConflictError(
                f"Skill '{name}' was modified (expected version {expected_version}, got {current_version})",
                skill_name=name,
                expected_version=expected_version,
                actual_version=current_version,
            )

        skill_dir = self._get_skill_dir(name)
        if not skill_dir.exists():
            with contextlib.suppress(Exception):
                db.mark_skill_registry_deleted(name, expected_version=current_version)
            raise SkillNotFoundError(name, detail="Skill directory not found")

        update_data: dict[str, Any] = {}
        if content is not None:
            try:
                parsed = self._parser.parse_content(content, default_name=name)
            except Exception as e:
                raise SkillValidationError(f"Invalid skill content: {e}") from e

            skill_file = skill_dir / "SKILL.md"
            try:
                skill_file.write_text(content, encoding="utf-8")
            except OSError as e:
                raise SkillStorageError(f"Failed to write SKILL.md: {e}", path=str(skill_file)) from e

            update_data.update(
                {
                    "description": parsed.frontmatter.description,
                    "argument_hint": parsed.frontmatter.argument_hint,
                    "disable_model_invocation": parsed.frontmatter.disable_model_invocation,
                    "user_invocable": parsed.frontmatter.user_invocable,
                    "allowed_tools": parsed.frontmatter.allowed_tools,
                    "model": parsed.frontmatter.model,
                    "context": parsed.frontmatter.context,
                    "directory_path": str(skill_dir),
                    "file_hash": parsed.content_hash,
                }
            )

        # Handle supporting files
        if supporting_files:
            for filename, file_content in supporting_files.items():
                file_path = skill_dir / filename
                if file_content is None:
                    if file_path.exists():
                        try:
                            file_path.unlink()
                        except OSError as e:
                            logger.warning(f"Failed to delete supporting file {filename}: {e}")
                else:
                    try:
                        file_path.write_text(file_content, encoding="utf-8")
                    except OSError as e:
                        logger.warning(f"Failed to write supporting file {filename}: {e}")

        if update_data:
            try:
                db.update_skill_registry(name, update_data, expected_version=current_version)
            except ConflictError as e:
                raise SkillConflictError(str(e), skill_name=name) from e
            except (CharactersRAGDBError, InputError) as e:
                raise SkillsError(f"Failed to update skill '{name}' in registry: {e}") from e

        logger.info(f"Updated skill '{name}' for user {self.user_id}")

        return await self.get_skill(name)

    async def delete_skill(self, name: str, expected_version: Optional[int] = None) -> None:
        """
        Delete a skill.

        Args:
            name: The skill name
            expected_version: Version for optimistic locking

        Raises:
            SkillNotFoundError: If skill doesn't exist
            SkillConflictError: If version mismatch
        """
        name = name.strip().lower()
        self._sync_registry()
        db = self._get_db()

        row = db.get_skill_registry(name, include_deleted=True)
        if not row:
            raise SkillNotFoundError(name)

        current_version = int(row.get("version") or 1)
        if expected_version is not None and current_version != expected_version:
            raise SkillConflictError(
                f"Skill '{name}' was modified (expected version {expected_version}, got {current_version})",
                skill_name=name,
                expected_version=expected_version,
                actual_version=current_version,
            )

        # Delete skill directory
        skill_dir = self._get_skill_dir(name)
        if skill_dir.exists():
            try:
                shutil.rmtree(skill_dir)
            except OSError as e:
                raise SkillStorageError(f"Failed to delete skill directory: {e}", path=str(skill_dir)) from e

        if not row.get("deleted"):
            try:
                db.mark_skill_registry_deleted(name, expected_version=current_version)
            except ConflictError as e:
                raise SkillConflictError(str(e), skill_name=name) from e
            except CharactersRAGDBError as e:
                raise SkillsError(f"Failed to delete skill '{name}' in registry: {e}") from e

        logger.info(f"Deleted skill '{name}' for user {self.user_id}")

    async def import_skill(
        self,
        content: str,
        name: Optional[str] = None,
        supporting_files: Optional[dict[str, str]] = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """
        Import a skill from content.

        Args:
            content: SKILL.md content
            name: Override name (otherwise extracted from frontmatter/content)
            supporting_files: Additional files to import
            overwrite: If True, overwrite existing skill

        Returns:
            Imported skill data
        """
        # Parse content to get name
        try:
            parsed = self._parser.parse_content(content, default_name=name)
        except Exception as e:
            raise SkillValidationError(f"Invalid skill content: {e}") from e

        skill_name = name or parsed.frontmatter.name
        if not skill_name:
            raise SkillValidationError("Skill name must be specified in frontmatter or as parameter")

        skill_name = skill_name.strip().lower()

        self._sync_registry()
        db = self._get_db()
        existing = db.get_skill_registry(skill_name, include_deleted=True)

        if existing and not existing.get("deleted"):
            if overwrite:
                await self.delete_skill(skill_name, expected_version=existing.get("version"))
            else:
                raise SkillConflictError(f"Skill '{skill_name}' already exists", skill_name=skill_name)

        return await self.create_skill(skill_name, content, supporting_files)

    async def import_from_zip(
        self,
        zip_data: bytes,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """
        Import a skill from a zip file.

        Args:
            zip_data: Zip file bytes
            overwrite: If True, overwrite existing skill

        Returns:
            Imported skill data
        """
        try:
            with zipfile.ZipFile(BytesIO(zip_data), "r") as zf:
                # Find SKILL.md
                skill_md_path = None
                base_dir = ""

                for name in zf.namelist():
                    if name.endswith("SKILL.md"):
                        skill_md_path = name
                        # Get the base directory
                        parts = name.split("/")
                        if len(parts) > 1:
                            base_dir = "/".join(parts[:-1]) + "/"
                        break

                if not skill_md_path:
                    raise SkillValidationError("Zip file does not contain SKILL.md")

                # Read SKILL.md
                content = zf.read(skill_md_path).decode("utf-8")

                # Read supporting files
                supporting_files: dict[str, str] = {}
                for name in zf.namelist():
                    if name == skill_md_path:
                        continue
                    if name.startswith(base_dir) and not name.endswith("/"):
                        relative_name = name[len(base_dir) :]
                        if relative_name and "/" not in relative_name:
                            try:
                                file_content = zf.read(name).decode("utf-8")
                                supporting_files[relative_name] = file_content
                            except UnicodeDecodeError:
                                logger.warning(f"Skipping non-text file: {name}")

                # Get skill name from directory
                skill_name = None
                if base_dir:
                    skill_name = base_dir.rstrip("/").split("/")[-1]

                return await self.import_skill(
                    content=content,
                    name=skill_name,
                    supporting_files=supporting_files or None,
                    overwrite=overwrite,
                )

        except zipfile.BadZipFile:
            raise SkillValidationError("Invalid zip file") from None

    async def export_skill(self, name: str) -> bytes:
        """
        Export a skill as a zip file.

        Args:
            name: The skill name

        Returns:
            Zip file bytes
        """
        skill_data = await self.get_skill(name)

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write SKILL.md with full content (including frontmatter)
            skill_dir = self._get_skill_dir(name)
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                full_content = skill_file.read_text(encoding="utf-8")
            else:
                # Reconstruct from parsed data
                fm = SkillFrontmatter(
                    name=skill_data["name"],
                    description=skill_data.get("description"),
                    argument_hint=skill_data.get("argument_hint"),
                    disable_model_invocation=skill_data.get("disable_model_invocation", False),
                    user_invocable=skill_data.get("user_invocable", True),
                    allowed_tools=skill_data.get("allowed_tools"),
                    model=skill_data.get("model"),
                    context=skill_data.get("context", "inline"),
                )
                full_content = self._parser.serialize_skill(fm, skill_data["content"])

            zf.writestr(f"{name}/SKILL.md", full_content)

            # Write supporting files
            supporting = skill_data.get("supporting_files", {})
            for filename, content in supporting.items():
                zf.writestr(f"{name}/{filename}", content)

        return buffer.getvalue()

    def get_context_payload(self) -> dict[str, Any]:
        """
        Get skill descriptions for context injection.

        Returns a dict with:
        - available_skills: list of skill summaries
        - context_text: formatted text for LLM context
        """
        self._sync_registry()
        db = self._get_db()
        rows = db.list_skill_registry(
            include_hidden=False,
            include_deleted=False,
            limit=10000,
            offset=0,
        )

        skills = [
            row for row in rows
            if row.get("user_invocable") and not row.get("disable_model_invocation")
        ]

        if not skills:
            return {
                "available_skills": [],
                "context_text": "",
            }

        # Build context text
        lines = ["<available-skills>"]
        for skill in sorted(skills, key=lambda s: s.get("name") or ""):
            hint = f" {skill.get('argument_hint')}" if skill.get("argument_hint") else ""
            desc = skill.get("description") or "No description"
            lines.append(f"- {skill.get('name')}{hint}: {desc}")
        lines.append("</available-skills>")

        return {
            "available_skills": [
                {
                    "name": s.get("name"),
                    "description": s.get("description"),
                    "argument_hint": s.get("argument_hint"),
                    "user_invocable": bool(s.get("user_invocable")),
                    "disable_model_invocation": bool(s.get("disable_model_invocation")),
                    "context": s.get("context", "inline"),
                }
                for s in skills
            ],
            "context_text": "\n".join(lines),
        }

    async def get_total_count(self, include_hidden: bool = False) -> int:
        """Get total count of skills."""
        self._sync_registry()
        db = self._get_db()
        return db.count_skill_registry(
            include_hidden=include_hidden,
            include_deleted=False,
        )
