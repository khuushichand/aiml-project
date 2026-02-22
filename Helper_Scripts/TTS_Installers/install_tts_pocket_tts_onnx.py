#!/usr/bin/env python3
"""
Download PocketTTS ONNX assets from HuggingFace.

Defaults (matches tts_providers_config.yaml):
  - ONNX dir     : models/pocket_tts_onnx/onnx
  - Tokenizer    : models/pocket_tts_onnx/tokenizer.model
  - Module path  : models/pocket_tts_onnx (pocket_tts_onnx.py or package)

Usage:
  python Helper_Scripts/TTS_Installers/install_tts_pocket_tts_onnx.py
  python Helper_Scripts/TTS_Installers/install_tts_pocket_tts_onnx.py --output-dir models/pocket_tts_onnx --force
  python Helper_Scripts/TTS_Installers/install_tts_pocket_tts_onnx.py --no-config-update
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from loguru import logger


def _download_repo(repo_id: str, output_dir: Path, onnx_subdir: str, tokenizer_name: str, force: bool) -> int:
    """
    Download PocketTTS assets from HuggingFace into the output directory.

    Args:
        repo_id: HuggingFace repository identifier.
        output_dir: Destination directory for assets.
        onnx_subdir: Repo subdirectory containing ONNX assets.
        tokenizer_name: Tokenizer filename in the repo.
        force: Whether to force re-download even if files exist.

    Returns:
        Exit code: 0 on success, 1 on download failure, 2 if huggingface_hub is missing.
    """
    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub import utils as hub_utils
    except ImportError as exc:
        logger.error(
            "huggingface_hub is required for this installer. Run: pip install -e '.[TTS_pocket_tts]'"
        )
        logger.opt(exception=exc).debug("huggingface_hub import error")
        return 2

    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    patterns = [
        f"{onnx_subdir}/**",
        f"{onnx_subdir}/*",
        tokenizer_name,
        "pocket_tts_onnx/**",
        "pocket_tts_onnx.py",
    ]

    download_error_types = [OSError, ValueError]
    for name in (
        "EntryNotFoundError",
        "GatedRepoError",
        "HFValidationError",
        "HfHubHTTPError",
        "LocalEntryNotFoundError",
        "RepositoryNotFoundError",
        "RevisionNotFoundError",
    ):
        exc_type = getattr(hub_utils, name, None)
        if isinstance(exc_type, type) and issubclass(exc_type, Exception):
            download_error_types.append(exc_type)

    try:
        snapshot_download(  # nosec B615
            repo_id=repo_id,
            local_dir=str(output_dir),
            local_dir_use_symlinks=False,
            allow_patterns=patterns,
            force_download=force,
        )
    except tuple(download_error_types) as exc:
        logger.error("Failed to download PocketTTS assets: {}", exc)
        logger.opt(exception=exc).debug("PocketTTS download failure")
        return 1

    return 0


def _validate_assets(output_dir: Path, onnx_subdir: str, tokenizer_name: str) -> int:
    """
    Validate that expected PocketTTS assets exist in the output directory.

    Args:
        output_dir: Directory containing the downloaded assets.
        onnx_subdir: Subdirectory containing ONNX assets.
        tokenizer_name: Tokenizer filename or directory name.

    Returns:
        Exit code: 0 when assets are present, 1 when missing.
    """
    onnx_dir = output_dir / onnx_subdir
    tokenizer_path = output_dir / tokenizer_name
    missing = []

    if not onnx_dir.exists() or not onnx_dir.is_dir():
        missing.append(str(onnx_dir))
    else:
        int8_files = [
            "flow_lm_main_int8.onnx",
            "flow_lm_flow_int8.onnx",
            "mimi_decoder_int8.onnx",
            "mimi_encoder.onnx",
            "text_conditioner.onnx",
        ]
        fp32_files = [
            "flow_lm_main.onnx",
            "flow_lm_flow.onnx",
            "mimi_decoder.onnx",
            "mimi_encoder.onnx",
            "text_conditioner.onnx",
        ]
        expected_metadata = ["LICENSE"]

        int8_missing = [name for name in int8_files if not (onnx_dir / name).exists()]
        fp32_missing = [name for name in fp32_files if not (onnx_dir / name).exists()]
        metadata_missing = [name for name in expected_metadata if not (onnx_dir / name).exists()]

        if metadata_missing:
            missing.extend(str(onnx_dir / name) for name in metadata_missing)

        if int8_missing and fp32_missing:
            missing.append(f"{onnx_dir} missing INT8 models: {', '.join(int8_missing)}")
            missing.append(f"{onnx_dir} missing FP32 models: {', '.join(fp32_missing)}")

    if not tokenizer_path.exists():
        missing.append(str(tokenizer_path))
    elif tokenizer_path.is_dir():
        tokenizer_candidates = [
            ["tokenizer.model"],
            ["tokenizer.json"],
            ["vocab.json", "merges.txt"],
            ["vocab.txt"],
        ]
        has_tokenizer_assets = any(
            all((tokenizer_path / name).exists() for name in files)
            for files in tokenizer_candidates
        )
        if not has_tokenizer_assets:
            missing.append(
                f"{tokenizer_path} missing tokenizer artifacts (expected tokenizer.model, tokenizer.json, "
                "vocab.json+merges.txt, or vocab.txt)"
            )
    elif not tokenizer_path.is_file():
        missing.append(str(tokenizer_path))

    if missing:
        logger.error("Missing expected PocketTTS assets.")
        for item in missing:
            logger.error("Missing asset: {}", item)
        return 1

    module_found = (output_dir / "pocket_tts_onnx.py").exists() or (output_dir / "pocket_tts_onnx").exists()
    if not module_found:
        logger.warning(
            "pocket_tts_onnx module not found in output directory. "
            "If import fails, set pocket_tts.module_path to the directory that contains the module."
        )

    return 0


def _resolve_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """
    Locate the repository root by walking parent directories.

    Args:
        start: Optional starting path to probe.

    Returns:
        The repo root path, or None if not found.
    """
    probe = start or Path(__file__).resolve()
    for anc in probe.parents:
        if (anc / ".git").exists():
            return anc
        if (anc / "pyproject.toml").exists() and (anc / "tldw_Server_API").is_dir():
            return anc
    return None


def _path_for_config(path: Path, repo_root: Optional[Path]) -> str:
    """
    Render a path suitable for config files, preferring repo-relative paths.

    Args:
        path: Path to convert.
        repo_root: Repository root to relativize against.

    Returns:
        A POSIX-style relative path when possible, otherwise an absolute path.
    """
    if not path.is_absolute():
        return path.as_posix()
    if repo_root:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError as exc:
            logger.debug(
                "relative_to failed for {} relative to {}: {}",
                path,
                repo_root,
                exc,
            )
    return str(path)


def _find_provider_block(lines: list[str], provider_name: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Find the YAML block for a provider inside a providers section.

    Args:
        lines: Config file lines.
        provider_name: Provider name to search for.

    Returns:
        A tuple of (block_start, block_end, block_indent) or (None, None, None).
    """
    in_providers = False
    providers_indent = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if not in_providers:
            if stripped == "providers:":
                in_providers = True
                providers_indent = indent
            continue
        if providers_indent is not None and indent <= providers_indent:
            in_providers = False
            continue
        if in_providers and stripped.startswith(f"{provider_name}:"):
            block_start = idx
            block_indent = indent
            end_idx = idx + 1
            while end_idx < len(lines):
                nxt = lines[end_idx]
                nxt_strip = nxt.strip()
                if not nxt_strip or nxt_strip.startswith("#"):
                    end_idx += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip(" "))
                if nxt_indent <= block_indent:
                    break
                end_idx += 1
            return block_start, end_idx, block_indent
    return None, None, None


def _render_value(value: object, quoted: bool) -> str:
    """
    Render a scalar value for YAML output.

    Args:
        value: Value to render.
        quoted: Whether to force double-quoted output.

    Returns:
        String representation suitable for YAML.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if quoted:
        return f"\"{value}\""
    return str(value)


def _upsert_key_line(
    lines: list[str],
    start: int,
    end: int,
    key: str,
    value: object,
    quoted: bool,
    key_indent: str,
) -> int:
    """
    Update or insert a key within a YAML provider block.

    Args:
        lines: Config lines to mutate in place.
        start: Start index for the provider block.
        end: End index for the provider block.
        key: YAML key to set.
        value: Value to assign.
        quoted: Whether to force double-quoted output.
        key_indent: Indentation string for the key.

    Returns:
        The (possibly updated) end index for the provider block.
    """
    needle = f"{key}:"
    for idx in range(start, end):
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith(needle):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent < len(key_indent):
            continue
        comment = None
        if "#" in line:
            _, comment = line.split("#", 1)
            comment = comment.strip()
        new_line = f"{key_indent}{key}: {_render_value(value, quoted)}"
        if comment:
            new_line += f"  # {comment}"
        lines[idx] = new_line
        return end

    lines.insert(end, f"{key_indent}{key}: {_render_value(value, quoted)}")
    return end + 1


def _update_config_file(
    config_path: Path,
    output_dir: Path,
    onnx_subdir: str,
    tokenizer_name: str,
    repo_root: Optional[Path],
) -> bool:
    """
    Update the PocketTTS provider paths in the config file.

    Args:
        config_path: Path to the tts_providers_config.yaml file.
        output_dir: Output directory containing assets.
        onnx_subdir: Subdirectory containing ONNX assets.
        tokenizer_name: Tokenizer filename or directory name.
        repo_root: Repository root used for relative path rendering.

    Returns:
        True when updates are applied, False when skipped.
    """
    if not config_path.exists():
        logger.warning("Config file not found at {}; skipping update.", config_path)
        return False

    content = config_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    block_start, block_end, block_indent = _find_provider_block(lines, "pocket_tts")
    if block_start is None or block_end is None or block_indent is None:
        logger.warning("providers.pocket_tts not found in config; skipping update.")
        return False

    key_indent = " " * (block_indent + 2)
    models_dir = output_dir / onnx_subdir
    updates = {
        "enabled": True,
        "model_path": _path_for_config(models_dir, repo_root),
        "tokenizer_path": _path_for_config(output_dir / tokenizer_name, repo_root),
        "module_path": _path_for_config(output_dir, repo_root),
    }

    block_end = _upsert_key_line(lines, block_start + 1, block_end, "enabled", updates["enabled"], False, key_indent)
    block_end = _upsert_key_line(
        lines, block_start + 1, block_end, "model_path", updates["model_path"], True, key_indent
    )
    block_end = _upsert_key_line(
        lines, block_start + 1, block_end, "tokenizer_path", updates["tokenizer_path"], True, key_indent
    )
    _upsert_key_line(lines, block_start + 1, block_end, "module_path", updates["module_path"], True, key_indent)

    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Updated config file: {}", config_path)
    return True


def _resolve_config_path(config_path_arg: Optional[str]) -> Optional[Path]:
    """
    Resolve the tts_providers_config.yaml path.

    Args:
        config_path_arg: Optional user-supplied config path.

    Returns:
        Resolved config path if found, otherwise None.
    """
    if config_path_arg:
        return Path(config_path_arg).expanduser()
    repo_root = _resolve_repo_root()
    if repo_root and str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from tldw_Server_API.app.core import config_paths
        return config_paths.resolve_module_yaml("tts")
    except ImportError as exc:
        if repo_root:
            candidate = repo_root / "tldw_Server_API" / "Config_Files" / "tts_providers_config.yaml"
            logger.warning(
                "config_paths import failed ({}); falling back to {}",
                exc,
                candidate,
            )
            logger.opt(exception=exc).debug("config_paths import error")
            return candidate
        logger.opt(exception=exc).debug("config_paths import error; no fallback path available")
    return None


def _check_module_import(output_dir: Path) -> bool:
    """
    Sanity-check that pocket_tts_onnx can be imported from the output directory.

    Args:
        output_dir: Directory containing pocket_tts_onnx.py or pocket_tts_onnx package.

    Returns:
        True if the module can be imported, False otherwise.
    """
    module_dir = output_dir
    module_dir_str = str(module_dir)
    added = False
    if module_dir_str not in sys.path:
        sys.path.insert(0, module_dir_str)
        added = True

    try:
        import importlib

        importlib.invalidate_caches()
        module = importlib.import_module("pocket_tts_onnx")
        if not hasattr(module, "PocketTTSOnnx"):
            logger.error("pocket_tts_onnx imported, but PocketTTSOnnx class not found.")
            return False
    except Exception as exc:
        logger.error("pocket_tts_onnx import check failed: {}", exc)
        logger.opt(exception=exc).debug("PocketTTS import failure")
        return False
    finally:
        if added:
            try:
                sys.path.remove(module_dir_str)
            except ValueError:
                pass

    return True


def main() -> int:
    """
    CLI entrypoint for downloading PocketTTS ONNX assets.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(description="Download PocketTTS ONNX assets from HuggingFace.")
    parser.add_argument("--repo-id", default="KevinAHM/pocket-tts-onnx", help="HuggingFace repo id")
    parser.add_argument("--output-dir", default="models/pocket_tts_onnx", help="Output directory for assets")
    parser.add_argument("--onnx-subdir", default="onnx", help="ONNX subdirectory in the repo")
    parser.add_argument("--tokenizer-name", default="tokenizer.model", help="Tokenizer filename in the repo")
    parser.add_argument("--force", action="store_true", help="Force re-download even if files exist")
    parser.add_argument("--config-path", default=None, help="Optional tts_providers_config.yaml path to update")
    parser.add_argument("--no-config-update", action="store_true", help="Skip updating tts_providers_config.yaml")
    parser.add_argument("--no-import-check", action="store_true", help="Skip sanity check for pocket_tts_onnx import")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()

    if not args.force and output_dir.exists():
        rc = _validate_assets(output_dir, str(args.onnx_subdir), str(args.tokenizer_name))
        if rc == 0:
            logger.info("Assets already present; use --force to re-download.")
            return 0
        logger.warning("Existing assets appear incomplete; continuing with download.")

    rc = _download_repo(
        repo_id=str(args.repo_id),
        output_dir=output_dir,
        onnx_subdir=str(args.onnx_subdir),
        tokenizer_name=str(args.tokenizer_name),
        force=bool(args.force),
    )
    if rc != 0:
        return rc

    rc = _validate_assets(output_dir, str(args.onnx_subdir), str(args.tokenizer_name))
    if rc != 0:
        return rc

    if not args.no_config_update:
        repo_root = _resolve_repo_root()
        config_path = _resolve_config_path(args.config_path)
        if config_path is None:
            logger.warning("Unable to resolve tts_providers_config.yaml; skipping update.")
        else:
            _update_config_file(
                config_path=config_path,
                output_dir=output_dir,
                onnx_subdir=str(args.onnx_subdir),
                tokenizer_name=str(args.tokenizer_name),
                repo_root=repo_root,
            )

    if not args.no_import_check:
        if not _check_module_import(output_dir):
            logger.error(
                "PocketTTS module is not importable. "
                "Ensure runtime deps are installed and module_path points to pocket_tts_onnx."
            )
            return 1

    logger.info("PocketTTS assets downloaded.")
    logger.info("  Models dir : {}", output_dir / args.onnx_subdir)
    logger.info("  Tokenizer  : {}", output_dir / args.tokenizer_name)
    logger.info("  Module path: {}", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
