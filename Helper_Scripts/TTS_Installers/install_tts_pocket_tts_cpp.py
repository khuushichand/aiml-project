#!/usr/bin/env python3
"""
Install and configure the PocketTTS.cpp native runtime.

This helper keeps `pocket_tts` (Python / ONNX) separate from `pocket_tts_cpp`
(native compiled binary runtime). The script exposes pure helper functions for
repo-root resolution, runtime layout construction, and config patching so they
can be unit-tested without running clone/build steps.

Expected runtime layout:
  bin/
    pocket-tts
  models/pocket_tts_cpp/
    tokenizer.model
    onnx/

The runtime build/export steps are explicit in the CLI path, but unit tests only
exercise the pure helpers.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from loguru import logger


DEFAULT_REPO_URL = "https://github.com/VolgaGerm/PocketTTS.cpp"
DEFAULT_RUNTIME_BASE = Path("models") / "pocket_tts_cpp"
DEFAULT_BINARY_PATH = Path("bin") / "pocket-tts"
DEFAULT_CONFIG_PATH = Path("tldw_Server_API") / "Config_Files" / "tts_providers_config.yaml"
PROVIDER_NAME = "pocket_tts_cpp"
INT8_MODEL_FILENAMES = (
    "flow_lm_main_int8.onnx",
    "flow_lm_flow_int8.onnx",
    "mimi_decoder_int8.onnx",
    "mimi_encoder.onnx",
    "text_conditioner.onnx",
)
FP32_MODEL_FILENAMES = (
    "flow_lm_main.onnx",
    "flow_lm_flow.onnx",
    "mimi_decoder.onnx",
    "mimi_encoder.onnx",
    "text_conditioner.onnx",
)


@dataclass(frozen=True)
class PocketTTSCppRuntimeLayout:
    """Resolved runtime paths for the native PocketTTS.cpp provider."""

    provider_name: str
    runtime_base: Path
    binary_path: Path
    tokenizer_path: Path
    model_dir: Path
    source_dir: Path
    build_dir: Path


def default_binary_name(platform_name: Optional[str] = None) -> str:
    """Return the repo-local binary name for the current platform."""

    platform_key = (platform_name or sys.platform).lower()
    if platform_key.startswith("win"):
        return "pocket-tts.exe"
    return "pocket-tts"


def resolve_repo_root(start: Optional[Path] = None) -> Path:
    """Resolve the repository root from a probe path."""

    probe = (start or Path(__file__)).resolve()
    candidates = (probe,) + tuple(probe.parents)
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists() and (candidate / "tldw_Server_API").is_dir():
            return candidate
    raise FileNotFoundError(f"Unable to resolve repository root from {probe}")


def build_runtime_layout(
    runtime_base: Path,
    repo_root: Optional[Path] = None,
    *,
    platform_name: Optional[str] = None,
) -> PocketTTSCppRuntimeLayout:
    """Build the expected PocketTTS.cpp runtime layout."""

    root = repo_root if repo_root is not None else resolve_repo_root()
    base_candidate = runtime_base.expanduser()
    base = base_candidate if base_candidate.is_absolute() else (root / base_candidate)
    return PocketTTSCppRuntimeLayout(
        provider_name=PROVIDER_NAME,
        runtime_base=base,
        binary_path=root / DEFAULT_BINARY_PATH.parent / default_binary_name(platform_name),
        tokenizer_path=base / "tokenizer.model",
        model_dir=base / "onnx",
        source_dir=root / "external" / "PocketTTS.cpp",
        build_dir=base / "_build",
    )


def _path_for_config(path: Path, repo_root: Optional[Path]) -> str:
    if not path.is_absolute():
        return path.as_posix()
    if repo_root is not None:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            pass
    return str(path)


def _render_yaml_value(value: object, quoted: bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if quoted:
        return f'"{value}"'
    return str(value)


def _find_provider_block(lines: list[str], provider_name: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    in_providers = False
    providers_indent: Optional[int] = None
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
        if stripped.startswith(f"{provider_name}:"):
            block_start = idx
            block_indent = indent
            block_end = idx + 1
            while block_end < len(lines):
                next_line = lines[block_end]
                next_stripped = next_line.strip()
                if not next_stripped or next_stripped.startswith("#"):
                    block_end += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip(" "))
                if next_indent <= block_indent:
                    break
                block_end += 1
            return block_start, block_end, block_indent
    return None, None, None


def _upsert_key_line(
    lines: list[str],
    start: int,
    end: int,
    key: str,
    value: object,
    quoted: bool,
    key_indent: str,
) -> int:
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
        new_line = f"{key_indent}{key}: {_render_yaml_value(value, quoted)}"
        if comment:
            new_line += f"  # {comment}"
        lines[idx] = new_line
        return end

    lines.insert(end, f"{key_indent}{key}: {_render_yaml_value(value, quoted)}")
    return end + 1


def _insert_provider_block(lines: list[str], provider_name: str, block_lines: list[str]) -> list[str]:
    block_start, block_end, block_indent = _find_provider_block(lines, provider_name)
    if block_start is not None and block_end is not None:
        lines[block_start:block_end] = block_lines
        return lines

    providers_start = None
    for idx, line in enumerate(lines):
        if line.strip() == "providers:":
            providers_start = idx
            break
    if providers_start is None:
        lines.extend(["", "providers:"])
        providers_start = len(lines) - 1

    insert_at = len(lines)
    providers_indent = len(lines[providers_start]) - len(lines[providers_start].lstrip(" "))
    for idx in range(providers_start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(lines[idx]) - len(lines[idx].lstrip(" "))
        if indent <= providers_indent:
            insert_at = idx
            break

    lines[insert_at:insert_at] = block_lines
    return lines


def patch_tts_config(
    config_path: Path,
    binary_path: Path,
    tokenizer_path: Path,
    model_dir: Path,
    repo_root: Optional[Path] = None,
) -> bool:
    """Patch the pocket_tts_cpp provider block without touching pocket_tts."""

    if not config_path.exists():
        logger.warning("Config file not found at {}; skipping update.", config_path)
        return False

    lines = config_path.read_text(encoding="utf-8").splitlines()
    block_start, block_end, block_indent = _find_provider_block(lines, PROVIDER_NAME)
    provider_indent = " " * (block_indent or 0)
    key_indent = provider_indent + "  "

    block_lines = [
        f"{provider_indent}{PROVIDER_NAME}:",
        f"{key_indent}enabled: true",
        f'{key_indent}binary_path: "{_path_for_config(binary_path, repo_root)}"',
        f'{key_indent}tokenizer_path: "{_path_for_config(tokenizer_path, repo_root)}"',
        f'{key_indent}model_path: "{_path_for_config(model_dir, repo_root)}"',
        f"{key_indent}device: cpu",
        f"{key_indent}sample_rate: 24000",
        f"{key_indent}enable_voice_cache: false",
        f"{key_indent}cache_ttl_hours: 24",
        f"{key_indent}cache_max_bytes_per_user: 1073741824",
        f"{key_indent}persist_direct_voice_references: false",
    ]

    if block_start is None or block_end is None or block_indent is None:
        lines = _insert_provider_block(lines, PROVIDER_NAME, block_lines)
    else:
        lines[block_start:block_end] = block_lines

    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Updated config file: {}", config_path)
    return True


def missing_prerequisite_commands(
    available_commands: Optional[Iterable[str]] = None,
    compiler_aliases: Sequence[str] = ("c++", "clang++", "g++"),
) -> list[str]:
    """Return the canonical prerequisite commands that are unavailable."""

    if available_commands is None:
        available = None
    else:
        available = {name for name in available_commands}

    missing: list[str] = []
    for command in ("git", "cmake"):
        if available is None:
            if shutil.which(command) is None:
                missing.append(command)
        elif command not in available:
            missing.append(command)

    if available is None:
        if not any(shutil.which(alias) for alias in compiler_aliases):
            missing.append("c++")
    elif not any(alias in available for alias in compiler_aliases):
        missing.append("c++")

    return missing


def _ensure_prerequisites() -> None:
    missing = missing_prerequisite_commands()
    if missing:
        raise SystemExit(f"Missing required command(s) on PATH: {', '.join(missing)}")


def _run_command(cmd: list[str], cwd: Optional[Path] = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)  # nosec B603


def clone_repository(repo_url: str, clone_dir: Path, branch: Optional[str] = None) -> Path:
    """Clone the PocketTTS.cpp repository."""

    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    if clone_dir.exists() and any(clone_dir.iterdir()):
        raise SystemExit(f"Clone directory already exists and is not empty: {clone_dir}")

    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([repo_url, str(clone_dir)])
    _run_command(cmd)
    return clone_dir


def configure_build(source_dir: Path, build_dir: Path, install_dir: Path) -> None:
    """Configure the CMake build for PocketTTS.cpp."""

    build_dir.mkdir(parents=True, exist_ok=True)
    cmake_args = [
        "cmake",
        "-S",
        str(source_dir),
        "-B",
        str(build_dir),
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
    ]
    _run_command(cmake_args)


def build_project(build_dir: Path) -> None:
    """Build the PocketTTS.cpp runtime."""

    _run_command(["cmake", "--build", str(build_dir), "--config", "Release"])


def install_project(build_dir: Path) -> None:
    """Install PocketTTS.cpp artifacts into the configured CMake install prefix."""

    _run_command(["cmake", "--install", str(build_dir), "--config", "Release"])


def export_runtime_artifacts(
    build_dir: Path,
    layout: PocketTTSCppRuntimeLayout,
    *,
    install_dir: Optional[Path] = None,
    built_binary_names: Sequence[str] = ("pocket-tts", "pocket-tts.exe", "pocket_tts_cpp", "pocket_tts_cpp.exe"),
    built_tokenizer_name: str = "tokenizer.model",
) -> None:
    """Copy the built runtime artifacts into the expected runtime layout."""

    layout.runtime_base.mkdir(parents=True, exist_ok=True)
    layout.model_dir.mkdir(parents=True, exist_ok=True)
    layout.binary_path.parent.mkdir(parents=True, exist_ok=True)

    candidate_roots = [root for root in (install_dir, build_dir) if root is not None]

    built_binary = next(
        (
            path
            for root in candidate_roots
            for binary_name in built_binary_names
            for path in (
                root / binary_name,
                root / "Release" / binary_name,
                root / "bin" / binary_name,
            )
            if path.exists()
        ),
        None,
    )
    if built_binary is None:
        logger.warning(
            "Built binary not found under {}; expected one of {}",
            build_dir,
            ", ".join(built_binary_names),
        )
    else:
        shutil.copy2(built_binary, layout.binary_path)

    tokenizer_candidates = [
        candidate
        for root in candidate_roots
        for candidate in (
            root / built_tokenizer_name,
            root / "assets" / built_tokenizer_name,
            root / "Release" / built_tokenizer_name,
        )
    ]
    built_tokenizer = next((path for path in tokenizer_candidates if path.exists()), None)
    if built_tokenizer is not None:
        shutil.copy2(built_tokenizer, layout.tokenizer_path)

    model_source_dir = next(
        (
            path
            for root in candidate_roots
            for path in (
                root / "onnx",
                root / "export" / "onnx",
                root / "models" / "onnx",
                root / "assets" / "onnx",
            )
            if path.exists() and path.is_dir()
        ),
        None,
    )
    if model_source_dir is None:
        logger.warning("Exported ONNX directory not found under {}", build_dir)
    else:
        for source in model_source_dir.iterdir():
            target = layout.model_dir / source.name
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target)


def validate_runtime_layout(layout: PocketTTSCppRuntimeLayout) -> list[str]:
    """Return a list of missing runtime artifacts required before enabling the provider."""

    missing: list[str] = []
    if not layout.binary_path.exists():
        missing.append(str(layout.binary_path))
    if not layout.tokenizer_path.exists():
        missing.append(str(layout.tokenizer_path))
    if not layout.model_dir.exists() or not layout.model_dir.is_dir():
        missing.append(str(layout.model_dir))
        return missing

    has_int8 = all((layout.model_dir / name).exists() for name in INT8_MODEL_FILENAMES)
    has_fp32 = all((layout.model_dir / name).exists() for name in FP32_MODEL_FILENAMES)
    if not has_int8 and not has_fp32:
        missing.append(
            f"{layout.model_dir} missing required PocketTTS.cpp ONNX exports "
            f"(expected one full INT8 or FP32 set)"
        )
    return missing


def _print_runtime_summary(layout: PocketTTSCppRuntimeLayout) -> None:
    print("PocketTTS.cpp runtime layout:")
    print(f"  Binary    : {layout.binary_path}")
    print(f"  Tokenizer : {layout.tokenizer_path}")
    print(f"  Models dir: {layout.model_dir}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install and configure the PocketTTS.cpp native TTS runtime."
    )
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="PocketTTS.cpp repository URL")
    parser.add_argument(
        "--runtime-base",
        default=str(DEFAULT_RUNTIME_BASE),
        help="Base runtime directory for the compiled provider",
    )
    parser.add_argument(
        "--source-dir",
        default=None,
        help="Optional existing PocketTTS.cpp source directory (skips clone when provided)",
    )
    parser.add_argument(
        "--build-dir",
        default=None,
        help="Optional build directory (defaults to <runtime-base>/_build)",
    )
    parser.add_argument(
        "--config-path",
        default=None,
        help="Path to tts_providers_config.yaml (defaults to repo copy)",
    )
    parser.add_argument("--branch", default=None, help="Optional git branch or tag to clone")
    parser.add_argument("--no-config-update", action="store_true", help="Skip config patching")
    parser.add_argument("--no-clone", action="store_true", help="Skip cloning the repository")
    parser.add_argument("--no-build", action="store_true", help="Skip the cmake configure/build steps")
    parser.add_argument("--no-export", action="store_true", help="Skip copying build outputs to runtime layout")
    args = parser.parse_args(argv)

    _ensure_prerequisites()

    repo_root = resolve_repo_root()
    runtime_base = Path(args.runtime_base).expanduser()
    layout = build_runtime_layout(runtime_base, repo_root=repo_root)
    build_dir = Path(args.build_dir).expanduser() if args.build_dir else layout.build_dir
    source_dir = Path(args.source_dir).expanduser() if args.source_dir else layout.source_dir

    if not args.no_clone and args.source_dir is None:
        clone_repository(args.repo_url, source_dir, branch=args.branch)

    if not args.no_build:
        configure_build(source_dir=source_dir, build_dir=build_dir, install_dir=runtime_base)
        build_project(build_dir=build_dir)
        install_project(build_dir=build_dir)

    if not args.no_export:
        export_runtime_artifacts(build_dir=build_dir, install_dir=runtime_base, layout=layout)

    missing_runtime = validate_runtime_layout(layout)
    if missing_runtime:
        raise SystemExit(
            "PocketTTS.cpp runtime export incomplete: " + "; ".join(missing_runtime)
        )

    if not args.no_config_update:
        config_path = (
            Path(args.config_path).expanduser()
            if args.config_path
            else repo_root / DEFAULT_CONFIG_PATH
        )
        patch_tts_config(
            config_path=config_path,
            binary_path=layout.binary_path,
            tokenizer_path=layout.tokenizer_path,
            model_dir=layout.model_dir,
            repo_root=repo_root,
        )

    _print_runtime_summary(layout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
