from __future__ import annotations

"""
Core helpers for sourcing media inputs (uploads, temp dirs).

This module centralizes logic that was previously implemented directly in
`_legacy_media.py` (TempDirManager and _save_uploaded_files) so that
process-only endpoints and future ingestion pipelines can share a single
implementation.

Behavior is intentionally kept backwards compatible with the original helpers.
"""

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path as FilePath, Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiofiles

from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import (
    FileValidationError,
    FileValidator,
    process_and_validate_file,
)
from tldw_Server_API.app.core.Utils.Utils import logging, sanitize_filename
from tldw_Server_API.app.core.Utils.Utils import logging as logger


class TempDirManager:
    """
    Context manager for temporary directories used during media processing.

    This is a direct extraction of the implementation previously defined in
    `_legacy_media.py`, with behavior preserved for compatibility.
    """

    def __init__(self, prefix: str = "media_processing_", *, cleanup: bool = True) -> None:
        self.temp_dir_path: Optional[FilePath] = None
        self.prefix = prefix
        self._cleanup = cleanup
        self._created = False

    def __enter__(self) -> FilePath:
        self.temp_dir_path = FilePath(tempfile.mkdtemp(prefix=self.prefix))
        self._created = True
        logging.info(f"Created temporary directory: {self.temp_dir_path}")
        return self.temp_dir_path

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._created and self.temp_dir_path and self._cleanup:
            # remove the fragile exists-check and always try to clean up
            try:
                shutil.rmtree(self.temp_dir_path, ignore_errors=True)
                logging.info(f"Cleaned up temporary directory: {self.temp_dir_path}")
            except Exception as e:  # pragma: no cover - defensive logging
                logging.error(
                    f"Failed to cleanup temporary directory {self.temp_dir_path}: {e}",
                    exc_info=True,
                )
        self.temp_dir_path = None
        self._created = False

    def get_path(self) -> FilePath:
        """
        Return the underlying temporary directory path.

        Raises:
            RuntimeError: if the directory has not been created or was cleaned up.
        """
        if not self._created or self.temp_dir_path is None:
            raise RuntimeError("Temporary directory not created or already cleaned up.")
        return self.temp_dir_path


async def save_uploaded_files(
    files: List["aiofiles.threadpool.binary.AsyncBufferedIOBase"],  # UploadFile duck type
    temp_dir: Path,
    validator: FileValidator,
    expected_media_type_key: Optional[str] = None,
    allowed_extensions: Optional[List[str]] = None,
    *,
    skip_archive_scanning: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Save uploaded files to a temporary directory, validating them via FileValidator.

    This is a direct extraction of `_save_uploaded_files` from `_legacy_media.py`.
    The signature and return contract are preserved so callers (including tests
    that exercise the helper via the media endpoints module) continue to work.

    Args:
        files: List of FastAPI `UploadFile`-like objects.
        temp_dir: Temporary directory where files will be written.
        validator: Shared `FileValidator` instance.
        expected_media_type_key: Optional media-type key hint used for validation.
        allowed_extensions: Optional list of allowed file extensions.
        skip_archive_scanning: When True, relaxes deep archive scanning for some types.

    Returns:
        processed_files: List of dicts for successfully saved files:
            `{"path": Path, "original_filename": str, "input_ref": str}`.
        file_handling_errors: List of dicts for failures:
            `{"original_filename": str, "input_ref": str, "status": "Error", "error": str}`.
    """
    processed_files: List[Dict[str, Any]] = []
    file_handling_errors: List[Dict[str, Any]] = []
    used_secure_names: Set[str] = set()

    normalized_allowed_extensions = {ext.lower().strip() for ext in allowed_extensions} if allowed_extensions else None
    logger.debug(f"Allowed extensions for upload: {normalized_allowed_extensions}")

    for file in files:
        original_filename = getattr(file, "filename", None)
        input_ref = original_filename or f"upload_{uuid.uuid4()}"
        local_file_path: Optional[Path] = None

        try:
            if not original_filename:
                logger.warning("Received file upload with no filename. Skipping.")
                file_handling_errors.append(
                    {
                        "original_filename": "N/A",
                        "input_ref": input_ref,
                        "status": "Error",
                        "error": "File uploaded without a filename.",
                    }
                )
                continue

            suffixes = [s.lower() for s in FilePath(original_filename).suffixes]
            candidates: List[str] = []
            for idx in range(len(suffixes)):
                joined = "".join(suffixes[idx:])
                if joined:
                    candidates.append(joined)
            file_extension = candidates[0] if candidates else FilePath(original_filename).suffix.lower()

            blocked_extensions = {
                ".exe",
                ".bat",
                ".cmd",
                ".com",
                ".scr",
                ".vbs",
                ".vbe",
                ".ws",
                ".wsf",
                ".wsc",
                ".wsh",
                ".ps1",
                ".ps1xml",
                ".ps2",
                ".ps2xml",
                ".psc1",
                ".psc2",
                ".msh",
                ".msh1",
                ".msh2",
                ".mshxml",
                ".msh1xml",
                ".msh2xml",
                ".scf",
                ".lnk",
                ".inf",
                ".reg",
                ".dll",
                ".app",
                ".sh",
                ".csh",
                ".ksh",
                ".bash",
                ".zsh",
                ".fish",
                ".jar",
                ".msi",
                ".dmg",
                ".pkg",
                ".deb",
                ".rpm",
                ".appimage",
                ".snap",
            }
            if expected_media_type_key == "code" or (normalized_allowed_extensions and ".js" in normalized_allowed_extensions):
                blocked_extensions.discard(".js")

            if file_extension in blocked_extensions:
                logger.warning(
                    f"Rejecting potentially dangerous file type '{file_extension}' for file '{original_filename}'"
                )
                file_handling_errors.append(
                    {
                        "original_filename": original_filename,
                        "input_ref": input_ref,
                        "status": "Error",
                        "error": f"File type '{file_extension}' is not allowed for security reasons",
                    }
                )
                continue

            if normalized_allowed_extensions and not any(
                c in normalized_allowed_extensions for c in (candidates or [file_extension])
            ):
                logger.warning(
                    f"Skipping file '{original_filename}' due to disallowed extension '{file_extension}'. "
                    f"Allowed: {allowed_extensions}"
                )
                file_handling_errors.append(
                    {
                        "original_filename": original_filename,
                        "input_ref": input_ref,
                        "status": "Error",
                        "error": (
                            f"Invalid file type ('{file_extension}'). "
                            f"Allowed extensions: {', '.join(allowed_extensions or [])}"
                        ),
                    }
                )
                continue

            original_stem = FilePath(original_filename).stem
            max_total_filename_len = 200
            secure_base = sanitize_filename(
                original_stem,
                max_total_length=max_total_filename_len,
                extension=file_extension,
            )

            def _build_filename(base: str, ext: str, suffix: Optional[str] = None) -> str:
                suffix_txt = f"_{suffix}" if suffix else ""
                reserved = len(suffix_txt) + len(ext)
                available = max_total_filename_len - reserved
                trunc_base = base if len(base) <= available else base[: max(1, available)]
                return f"{trunc_base}{suffix_txt}{ext}"

            secure_filename = _build_filename(secure_base, file_extension)
            counter = 0
            temp_path_to_check = temp_dir / secure_filename
            while secure_filename in used_secure_names or temp_path_to_check.exists():
                counter += 1
                secure_filename = _build_filename(secure_base, file_extension, str(counter))
                temp_path_to_check = temp_dir / secure_filename
                if counter > 100:
                    raise OSError(
                        f"Could not generate unique filename for {original_filename} after {counter} attempts."
                    )

            used_secure_names.add(secure_filename)
            local_file_path = temp_dir / secure_filename

            logger.info(
                f"Attempting to save uploaded file '{original_filename}' securely as: {local_file_path}"
            )

            inferred_media_key: Optional[str] = None
            if candidates:
                if any(
                    c
                    in {
                        ".mp4",
                        ".avi",
                        ".mov",
                        ".mkv",
                        ".webm",
                        ".flv",
                        ".wmv",
                        ".mpg",
                        ".mpeg",
                    }
                    for c in candidates
                ):
                    inferred_media_key = "video"
                elif any(
                    c
                    in {
                        ".mp3",
                        ".aac",
                        ".flac",
                        ".wav",
                        ".ogg",
                        ".m4a",
                        ".wma",
                    }
                    for c in candidates
                ):
                    inferred_media_key = "audio"
                elif any(c in {".pdf"} for c in candidates):
                    inferred_media_key = "pdf"
                elif any(c in {".epub", ".mobi", ".azw"} for c in candidates):
                    inferred_media_key = "ebook"
                elif any(c in {".eml", ".mbox", ".pst", ".ost"} for c in candidates):
                    inferred_media_key = "email"
                elif any(c in {".html", ".htm"} for c in candidates):
                    inferred_media_key = "html"
                elif any(c in {".xml", ".opml"} for c in candidates):
                    inferred_media_key = "xml"
                elif any(c in {".txt", ".md", ".docx", ".rtf", ".json"} for c in candidates):
                    inferred_media_key = "document"
                elif any(
                    c
                    in {
                        ".zip",
                        ".tar",
                        ".tgz",
                        ".tar.gz",
                        ".tbz2",
                        ".tar.bz2",
                        ".txz",
                        ".tar.xz",
                    }
                    for c in candidates
                ):
                    inferred_media_key = "archive"
                elif any(
                    c
                    in {
                        ".py",
                        ".c",
                        ".h",
                        ".cpp",
                        ".hpp",
                        ".cc",
                        ".cxx",
                        ".cs",
                        ".java",
                        ".kt",
                        ".kts",
                        ".swift",
                        ".rs",
                        ".go",
                        ".rb",
                        ".php",
                        ".pl",
                        ".lua",
                        ".sql",
                        ".yaml",
                        ".yml",
                        ".toml",
                        ".ini",
                        ".cfg",
                        ".conf",
                        ".ts",
                        ".tsx",
                        ".jsx",
                        ".js",
                    }
                    for c in candidates
                ):
                    inferred_media_key = "code"

            max_cfg_bytes: Optional[int] = None
            try:
                cfg = validator.get_media_config(inferred_media_key)
                if cfg:
                    if inferred_media_key == "archive":
                        size_mb = cfg.get("archive_file_size_mb") or cfg.get("max_size_mb")
                    else:
                        size_mb = cfg.get("max_size_mb")
                    if isinstance(size_mb, (int, float)):
                        max_cfg_bytes = int(size_mb) * 1024 * 1024
            except Exception:
                max_cfg_bytes = None

            written = 0
            try:
                async with aiofiles.open(local_file_path, "wb") as buffer:
                    while True:
                        chunk = await file.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if max_cfg_bytes and written > max_cfg_bytes:
                            raise ValueError(
                                f"File size ({written} bytes) exceeds maximum allowed size "
                                f"({max_cfg_bytes} bytes) for {inferred_media_key or 'file'}"
                            )
                        await buffer.write(chunk)
            except Exception as write_err:
                try:
                    if local_file_path is not None:
                        local_file_path.unlink(missing_ok=True)
                except OSError as unlink_err:  # pragma: no cover - defensive
                    logger.warning(
                        f"Failed to remove partially written upload file: {local_file_path}: {unlink_err}",
                        exc_info=True,
                    )
                file_handling_errors.append(
                    {
                        "original_filename": original_filename,
                        "input_ref": input_ref,
                        "status": "Error",
                        "error": str(write_err),
                    }
                )
                continue

            if written == 0:
                logger.warning(f"Uploaded file '{original_filename}' is empty. Skipping.")
                file_handling_errors.append(
                    {
                        "original_filename": original_filename,
                        "input_ref": input_ref,
                        "status": "Error",
                        "error": "Uploaded file content is empty.",
                    }
                )
                try:
                    if local_file_path is not None:
                        local_file_path.unlink(missing_ok=True)
                except OSError as unlink_err:  # pragma: no cover - defensive
                    logger.warning(
                        f"Failed to remove empty upload file: {local_file_path}: {unlink_err}",
                        exc_info=True,
                    )
                continue

            try:
                archive_exts = {
                    ".zip",
                    ".tar",
                    ".tgz",
                    ".tar.gz",
                    ".tbz2",
                    ".tar.bz2",
                    ".txz",
                    ".tar.xz",
                }
                is_pst_ost = file_extension in {".pst", ".ost"}
                pst_accepted = normalized_allowed_extensions is not None and (
                    ".pst" in normalized_allowed_extensions or ".ost" in normalized_allowed_extensions
                )

                if skip_archive_scanning and file_extension in archive_exts:
                    validation_result = validator.validate_file(
                        local_file_path,
                        original_filename=original_filename,
                        media_type_key="archive",
                    )
                elif is_pst_ost and pst_accepted:
                    validation_result = validator.validate_file(
                        local_file_path,
                        original_filename=original_filename,
                        media_type_key="email",
                        allowed_mimetypes_override=set(),
                    )
                else:
                    try:
                        from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import (
                            _resolve_media_type_key as _resolve_media_type_key_for_upload,
                        )

                        inferred_media_key = _resolve_media_type_key_for_upload(
                            original_filename or str(local_file_path)
                        )
                    except Exception:
                        inferred_media_key = None
                    media_key_override = inferred_media_key or expected_media_type_key
                    validation_result = process_and_validate_file(
                        local_file_path,
                        validator,
                        original_filename=original_filename,
                        media_type_key_override=media_key_override,
                    )
            except FileValidationError as validation_err:
                issues = getattr(validation_err, "issues", None) or [str(validation_err)]
                logger.warning(
                    f"Validation raised error for uploaded file '{original_filename}': {issues}"
                )
                file_handling_errors.append(
                    {
                        "original_filename": original_filename,
                        "input_ref": input_ref,
                        "status": "Error",
                        "error": f"Validation error: {'; '.join(issues)}",
                    }
                )
                if local_file_path is not None and local_file_path.exists():
                    local_file_path.unlink(missing_ok=True)
                continue
            except Exception as validation_exc:
                logger.error(
                    f"Unexpected error validating uploaded file '{original_filename}': {validation_exc}",
                    exc_info=True,
                )
                file_handling_errors.append(
                    {
                        "original_filename": original_filename,
                        "input_ref": input_ref,
                        "status": "Error",
                        "error": f"Validation error: {type(validation_exc).__name__} - {validation_exc}",
                    }
                )
                if local_file_path is not None and local_file_path.exists():
                    local_file_path.unlink(missing_ok=True)
                continue

            if not validation_result:
                issue_msg = "; ".join(getattr(validation_result, "issues", None) or ["Unknown validation failure"])
                logger.warning(
                    f"Validation failed for uploaded file '{original_filename}': {issue_msg}"
                )
                file_handling_errors.append(
                    {
                        "original_filename": original_filename,
                        "input_ref": input_ref,
                        "status": "Error",
                        "error": f"Validation failed: {issue_msg}",
                    }
                )
                if local_file_path is not None and local_file_path.exists():
                    local_file_path.unlink(missing_ok=True)
                continue

            file_size = local_file_path.stat().st_size
            logger.info(f"Successfully saved '{original_filename}' ({file_size} bytes) to {local_file_path}")

            processed_files.append(
                {
                    "path": local_file_path,
                    "original_filename": original_filename,
                    "input_ref": input_ref,
                }
            )

        except Exception as e:
            logger.error(
                f"Failed to save or validate uploaded file '{original_filename or input_ref}': {e}",
                exc_info=True,
            )
            file_handling_errors.append(
                {
                    "original_filename": original_filename or "N/A",
                    "input_ref": input_ref,
                    "status": "Error",
                    "error": f"Failed during upload processing: {type(e).__name__} - {e}",
                }
            )
            if local_file_path is not None and local_file_path.exists():
                try:
                    local_file_path.unlink(missing_ok=True)
                    logger.debug(f"Cleaned up partially saved/failed file: {local_file_path}")
                except OSError as unlink_err:  # pragma: no cover - defensive
                    logger.warning(
                        f"Failed to clean up partially saved/failed file {local_file_path}: {unlink_err}"
                    )
        finally:
            # Ensure the UploadFile is closed, releasing resources
            close = getattr(file, "close", None)
            if asyncio.iscoroutinefunction(close):
                await close()  # type: ignore[arg-type]
            elif callable(close):
                close()

    return processed_files, file_handling_errors


__all__ = ["TempDirManager", "save_uploaded_files"]

