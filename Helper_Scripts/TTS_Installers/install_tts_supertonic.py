#!/usr/bin/env python
"""
Supertonic ONNX installer helper.

This script clones the upstream Supertonic assets (requires git + git-lfs),
copies ONNX models and voice style JSONs into the expected layout, and prints
a config snippet for tts_providers_config.yaml.

Default paths:
- ONNX models: models/supertonic/onnx
- Voice styles: models/supertonic/voice_styles
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List, Tuple


DEFAULT_REPO_URL = "https://huggingface.co/Supertone/supertonic"
DEFAULT_BASE = Path("models") / "supertonic"
REQUIRED_ONNX_FILES = {
    "duration_predictor.onnx",
    "text_encoder.onnx",
    "vector_estimator.onnx",
    "vocoder.onnx",
    "tts.json",
    "unicode_indexer.json",
}


def _run(cmd: List[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _ensure_tool(name: str) -> None:
    if shutil.which(name):
        return
    raise SystemExit(f"Required tool not found on PATH: {name}. Please install it first.")


def _copy_files(paths: Iterable[Path], dest: Path, overwrite: bool) -> List[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    copied: List[Path] = []
    for src in paths:
        target = dest / src.name
        if target.exists() and not overwrite:
            print(f"Skipping existing file: {target}")
            continue
        shutil.copy2(src, target)
        copied.append(target)
    return copied


def _find_voice_jsons(clone_dir: Path) -> List[Path]:
    voice_dirs = [p for p in clone_dir.rglob("*") if p.is_dir() and p.name.lower() in {"voice_styles", "voices"}]
    search_roots = voice_dirs or [clone_dir]
    jsons: List[Path] = []
    for root in search_roots:
        for path in root.rglob("*.json"):
            jsons.append(path)
    return jsons


def _infer_voice_ids(copied_jsons: List[Path]) -> List[Tuple[str, Path]]:
    mappings: List[Tuple[str, Path]] = []
    for path in copied_jsons:
        stem = path.stem.lower()
        vid = path.stem  # default to filename stem
        if "m1" in stem or "male" in stem:
            vid = "supertonic_m1"
        elif "f1" in stem or "female" in stem:
            vid = "supertonic_f1"
        mappings.append((vid, path))
    return mappings


def _print_config_snippet(onnx_dir: Path, voice_dir: Path, voice_map: List[Tuple[str, Path]]) -> None:
    voice_lines = [f"        {vid}: \"{p.name}\"" for vid, p in voice_map] or ["        supertonic_m1: \"M1.json\""]
    snippet = f"""
Config snippet (add under providers.supertonic):

providers:
  supertonic:
    enabled: true
    model_path: "{onnx_dir}"
    sample_rate: 24000
    device: "cpu"
    extra_params:
      voice_styles_dir: "{voice_dir}"
      default_voice: "{voice_map[0][0] if voice_map else 'supertonic_m1'}"
      voice_files:
{os.linesep.join(voice_lines)}
      default_total_step: 5
      default_speed: 1.05
      n_test: 1
"""
    print(snippet.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Supertonic ONNX assets")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Source repository URL")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE), help="Base directory for Supertonic assets")
    parser.add_argument("--onnx-dir", default="onnx", help="Subdirectory (under base) for ONNX models")
    parser.add_argument("--voice-styles-dir", default="voice_styles", help="Subdirectory (under base) for voice styles")
    parser.add_argument("--keep-clone", action="store_true", help="Keep the cloned repository")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    _ensure_tool("git")
    _ensure_tool("git-lfs")

    base_dir = Path(args.base_dir).expanduser()
    onnx_dir = (base_dir / args.onnx_dir).expanduser()
    voice_dir = (base_dir / args.voice_styles_dir).expanduser()

    clone_root = base_dir / "_supertonic_clone" if args.keep_clone else Path(tempfile.mkdtemp(prefix="supertonic_clone_"))
    if clone_root.exists():
        if any(clone_root.iterdir()):
            raise SystemExit(f"Clone directory already exists and is not empty: {clone_root}")
    clone_root.parent.mkdir(parents=True, exist_ok=True)

    try:
        print("Installing git lfs filters...")
        _run(["git", "lfs", "install"])

        print(f"Cloning {args.repo_url} -> {clone_root}")
        _run(["git", "clone", "--depth", "1", args.repo_url, str(clone_root)])

        onnx_files = list(clone_root.rglob("*.onnx"))
        meta_files = [p for p in clone_root.rglob("*.json") if p.name in {"tts.json", "unicode_indexer.json"}]
        if not onnx_files:
            print("Warning: No .onnx files found in the cloned repository.")
        copied_onnx = _copy_files(onnx_files + meta_files, onnx_dir, args.overwrite)
        missing_required = REQUIRED_ONNX_FILES - {p.name for p in copied_onnx}
        if missing_required:
            print(f"Warning: missing expected files in onnx_dir: {', '.join(sorted(missing_required))}")
        print(f"Copied {len(copied_onnx)} ONNX/meta file(s) to {onnx_dir}")

        voice_jsons = _find_voice_jsons(clone_root)
        if not voice_jsons:
            print("Warning: No voice style JSON files found.")
        copied_voice_jsons = _copy_files(voice_jsons, voice_dir, args.overwrite)
        voice_map = _infer_voice_ids(copied_voice_jsons)
        print(f"Copied {len(copied_voice_jsons)} voice style file(s) to {voice_dir}")

        _print_config_snippet(onnx_dir, voice_dir, voice_map)
        print("Done. Update tldw_Server_API/Config_Files/tts_providers_config.yaml with the snippet above.")
    finally:
        if not args.keep_clone and clone_root.exists():
            shutil.rmtree(clone_root, ignore_errors=True)


if __name__ == "__main__":
    main()
