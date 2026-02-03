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

import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from tldw_Server_API.app.core.Skills.exceptions import (
    SkillConflictError,
    SkillNotFoundError,
    SkillsError,
    SkillStorageError,
    SkillValidationError,
)
from tldw_Server_API.app.core.Skills.skill_parser import SkillFrontmatter, SkillParser

# Simple JSON metadata file for tracking skill metadata
SKILLS_INDEX_FILE = "_skills_index.json"


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

    def __init__(self, user_id: int, base_path: Path):
        """
        Initialize the SkillsService.

        Args:
            user_id: The user ID for skill isolation
            base_path: Base path for user databases (e.g., Databases/user_databases/{user_id}/)
        """
        self.user_id = user_id
        self.base_path = Path(base_path)
        self.skills_dir = self.base_path / "skills"
        self._parser = SkillParser()
        self._ensure_skills_directory()

    def _ensure_skills_directory(self) -> None:
        """Ensure the skills directory exists."""
        try:
            self.skills_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise SkillStorageError(
                f"Failed to create skills directory: {e}",
                path=str(self.skills_dir),
            )

    def _get_index_path(self) -> Path:
        """Get the path to the skills index file."""
        return self.skills_dir / SKILLS_INDEX_FILE

    def _load_index(self) -> dict[str, SkillMetadata]:
        """Load the skills index from disk."""
        index_path = self._get_index_path()
        if not index_path.exists():
            return {}

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                name: SkillMetadata.from_dict(skill_data)
                for name, skill_data in data.get("skills", {}).items()
            }
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load skills index: {e}")
            return {}

    def _save_index(self, index: dict[str, SkillMetadata]) -> None:
        """Save the skills index to disk."""
        index_path = self._get_index_path()
        try:
            data = {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "skills": {name: meta.to_dict() for name, meta in index.items()},
            }
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Failed to save skills index: {e}")
            raise SkillStorageError(f"Failed to save skills index: {e}", path=str(index_path))

    def _get_skill_dir(self, name: str) -> Path:
        """Get the directory path for a skill."""
        return self.skills_dir / name

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
        index = self._load_index()

        # Synchronize index with filesystem
        self._sync_index(index)

        skills = list(index.values())

        # Filter hidden skills
        if not include_hidden:
            skills = [s for s in skills if s.user_invocable]

        # Sort by name
        skills.sort(key=lambda s: s.name)

        # Apply pagination
        return skills[offset : offset + limit]

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
        index = self._load_index()

        if name not in index:
            raise SkillNotFoundError(name)

        metadata = index[name]
        skill_dir = self._get_skill_dir(name)

        if not skill_dir.exists():
            # Skill directory was deleted, remove from index
            del index[name]
            self._save_index(index)
            raise SkillNotFoundError(name, detail="Skill directory not found")

        try:
            parsed = self._parser.parse_directory(skill_dir)
        except Exception as e:
            raise SkillsError(f"Failed to parse skill: {e}")

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
        index = self._load_index()

        if name in index:
            raise SkillConflictError(f"Skill '{name}' already exists", skill_name=name)

        # Parse the content to validate
        try:
            parsed = self._parser.parse_content(content, default_name=name)
        except Exception as e:
            raise SkillValidationError(f"Invalid skill content: {e}")

        # Create skill directory
        skill_dir = self._get_skill_dir(name)
        try:
            skill_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise SkillConflictError(f"Skill directory '{name}' already exists", skill_name=name)
        except OSError as e:
            raise SkillStorageError(f"Failed to create skill directory: {e}", path=str(skill_dir))

        # Write SKILL.md
        skill_file = skill_dir / "SKILL.md"
        try:
            skill_file.write_text(content, encoding="utf-8")
        except OSError as e:
            shutil.rmtree(skill_dir, ignore_errors=True)
            raise SkillStorageError(f"Failed to write SKILL.md: {e}", path=str(skill_file))

        # Write supporting files
        if supporting_files:
            for filename, file_content in supporting_files.items():
                if file_content is None:
                    continue
                try:
                    (skill_dir / filename).write_text(file_content, encoding="utf-8")
                except OSError as e:
                    logger.warning(f"Failed to write supporting file {filename}: {e}")

        # Create metadata
        now = datetime.now(timezone.utc)
        metadata = SkillMetadata(
            id=str(uuid.uuid4()),
            name=name,
            description=parsed.frontmatter.description,
            argument_hint=parsed.frontmatter.argument_hint,
            disable_model_invocation=parsed.frontmatter.disable_model_invocation,
            user_invocable=parsed.frontmatter.user_invocable,
            allowed_tools=parsed.frontmatter.allowed_tools,
            model=parsed.frontmatter.model,
            context=parsed.frontmatter.context,
            directory_path=str(skill_dir),
            content_hash=parsed.content_hash,
            created_at=now,
            last_modified=now,
            version=1,
        )

        # Update index
        index[name] = metadata
        self._save_index(index)

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
        index = self._load_index()

        if name not in index:
            raise SkillNotFoundError(name)

        metadata = index[name]

        # Check version for optimistic locking
        if expected_version is not None and metadata.version != expected_version:
            raise SkillConflictError(
                f"Skill '{name}' was modified (expected version {expected_version}, got {metadata.version})",
                skill_name=name,
                expected_version=expected_version,
                actual_version=metadata.version,
            )

        skill_dir = self._get_skill_dir(name)
        if not skill_dir.exists():
            del index[name]
            self._save_index(index)
            raise SkillNotFoundError(name, detail="Skill directory not found")

        # Update SKILL.md if provided
        if content is not None:
            try:
                parsed = self._parser.parse_content(content, default_name=name)
            except Exception as e:
                raise SkillValidationError(f"Invalid skill content: {e}")

            skill_file = skill_dir / "SKILL.md"
            try:
                skill_file.write_text(content, encoding="utf-8")
            except OSError as e:
                raise SkillStorageError(f"Failed to write SKILL.md: {e}", path=str(skill_file))

            # Update metadata from parsed content
            metadata.description = parsed.frontmatter.description
            metadata.argument_hint = parsed.frontmatter.argument_hint
            metadata.disable_model_invocation = parsed.frontmatter.disable_model_invocation
            metadata.user_invocable = parsed.frontmatter.user_invocable
            metadata.allowed_tools = parsed.frontmatter.allowed_tools
            metadata.model = parsed.frontmatter.model
            metadata.context = parsed.frontmatter.context
            metadata.content_hash = parsed.content_hash

        # Handle supporting files
        if supporting_files:
            for filename, file_content in supporting_files.items():
                file_path = skill_dir / filename
                if file_content is None:
                    # Delete the file
                    if file_path.exists():
                        try:
                            file_path.unlink()
                        except OSError as e:
                            logger.warning(f"Failed to delete supporting file {filename}: {e}")
                else:
                    # Create/update the file
                    try:
                        file_path.write_text(file_content, encoding="utf-8")
                    except OSError as e:
                        logger.warning(f"Failed to write supporting file {filename}: {e}")

        # Update metadata
        metadata.last_modified = datetime.now(timezone.utc)
        metadata.version += 1

        index[name] = metadata
        self._save_index(index)

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
        index = self._load_index()

        if name not in index:
            raise SkillNotFoundError(name)

        metadata = index[name]

        if expected_version is not None and metadata.version != expected_version:
            raise SkillConflictError(
                f"Skill '{name}' was modified (expected version {expected_version}, got {metadata.version})",
                skill_name=name,
                expected_version=expected_version,
                actual_version=metadata.version,
            )

        # Delete skill directory
        skill_dir = self._get_skill_dir(name)
        if skill_dir.exists():
            try:
                shutil.rmtree(skill_dir)
            except OSError as e:
                raise SkillStorageError(f"Failed to delete skill directory: {e}", path=str(skill_dir))

        # Remove from index
        del index[name]
        self._save_index(index)

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
            raise SkillValidationError(f"Invalid skill content: {e}")

        skill_name = name or parsed.frontmatter.name
        if not skill_name:
            raise SkillValidationError("Skill name must be specified in frontmatter or as parameter")

        skill_name = skill_name.strip().lower()

        index = self._load_index()

        if skill_name in index:
            if overwrite:
                await self.delete_skill(skill_name)
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
                        if relative_name and not "/" in relative_name:
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
            raise SkillValidationError("Invalid zip file")

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
        index = self._load_index()
        self._sync_index(index)

        # Filter to user-invocable skills that can be auto-invoked
        skills = [
            s for s in index.values()
            if s.user_invocable and not s.disable_model_invocation
        ]

        if not skills:
            return {
                "available_skills": [],
                "context_text": "",
            }

        # Build context text
        lines = ["<available-skills>"]
        for skill in sorted(skills, key=lambda s: s.name):
            hint = f" {skill.argument_hint}" if skill.argument_hint else ""
            desc = skill.description or "No description"
            lines.append(f"- {skill.name}{hint}: {desc}")
        lines.append("</available-skills>")

        return {
            "available_skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "argument_hint": s.argument_hint,
                    "user_invocable": s.user_invocable,
                    "disable_model_invocation": s.disable_model_invocation,
                    "context": s.context,
                }
                for s in skills
            ],
            "context_text": "\n".join(lines),
        }

    def _sync_index(self, index: dict[str, SkillMetadata]) -> None:
        """
        Synchronize the index with the filesystem.

        - Add skills that exist on disk but not in index
        - Remove skills from index that no longer exist on disk
        """
        changed = False

        # Find skills on disk
        if self.skills_dir.exists():
            disk_skills = set()
            for item in self.skills_dir.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    disk_skills.add(item.name)

            # Add missing skills
            for name in disk_skills:
                if name not in index:
                    try:
                        parsed = self._parser.parse_directory(self._get_skill_dir(name))
                        now = datetime.now(timezone.utc)
                        index[name] = SkillMetadata(
                            id=str(uuid.uuid4()),
                            name=name,
                            description=parsed.frontmatter.description,
                            argument_hint=parsed.frontmatter.argument_hint,
                            disable_model_invocation=parsed.frontmatter.disable_model_invocation,
                            user_invocable=parsed.frontmatter.user_invocable,
                            allowed_tools=parsed.frontmatter.allowed_tools,
                            model=parsed.frontmatter.model,
                            context=parsed.frontmatter.context,
                            directory_path=str(self._get_skill_dir(name)),
                            content_hash=parsed.content_hash,
                            created_at=now,
                            last_modified=now,
                            version=1,
                        )
                        changed = True
                        logger.info(f"Discovered skill '{name}' on disk")
                    except Exception as e:
                        logger.warning(f"Failed to index skill '{name}': {e}")

            # Remove missing skills
            for name in list(index.keys()):
                if name not in disk_skills:
                    del index[name]
                    changed = True
                    logger.info(f"Removed stale skill '{name}' from index")

        if changed:
            self._save_index(index)

    async def get_total_count(self, include_hidden: bool = False) -> int:
        """Get total count of skills."""
        index = self._load_index()
        self._sync_index(index)

        if include_hidden:
            return len(index)
        return sum(1 for s in index.values() if s.user_invocable)
