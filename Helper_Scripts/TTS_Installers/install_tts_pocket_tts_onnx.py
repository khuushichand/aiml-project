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
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _download_repo(repo_id: str, output_dir: Path, onnx_subdir: str, tokenizer_name: str, force: bool) -> int:
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        print(
            "ERROR: huggingface_hub is required for this installer. "
            "Run: pip install -e '.[TTS_pocket_tts]'",
            file=sys.stderr,
        )
        print(f"Details: {exc}", file=sys.stderr)
        return 2

    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    patterns = [
        f"{onnx_subdir}/**",
        f"{onnx_subdir}/*",
        tokenizer_name,
        "pocket_tts_onnx/**",
        "pocket_tts_onnx.py",
    ]

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(output_dir),
            local_dir_use_symlinks=False,
            allow_patterns=patterns,
            force_download=force,
        )
    except Exception as exc:
        print(f"ERROR: failed to download PocketTTS assets: {exc}", file=sys.stderr)
        return 1

    return 0


def _validate_assets(output_dir: Path, onnx_subdir: str, tokenizer_name: str) -> int:
    onnx_dir = output_dir / onnx_subdir
    tokenizer_path = output_dir / tokenizer_name
    missing = []

    if not onnx_dir.exists() or not any(onnx_dir.iterdir()):
        missing.append(str(onnx_dir))
    if not tokenizer_path.exists():
        missing.append(str(tokenizer_path))

    if missing:
        print("ERROR: missing expected PocketTTS assets:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        return 1

    module_found = (output_dir / "pocket_tts_onnx.py").exists() or (output_dir / "pocket_tts_onnx").exists()
    if not module_found:
        print(
            "WARNING: pocket_tts_onnx module not found in output directory. "
            "If import fails, set pocket_tts.module_path to the directory that contains the module.",
            file=sys.stderr,
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Download PocketTTS ONNX assets from HuggingFace.")
    parser.add_argument("--repo-id", default="KevinAHM/pocket-tts-onnx", help="HuggingFace repo id")
    parser.add_argument("--output-dir", default="models/pocket_tts_onnx", help="Output directory for assets")
    parser.add_argument("--onnx-subdir", default="onnx", help="ONNX subdirectory in the repo")
    parser.add_argument("--tokenizer-name", default="tokenizer.model", help="Tokenizer filename in the repo")
    parser.add_argument("--force", action="store_true", help="Force re-download even if files exist")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()

    if not args.force and output_dir.exists():
        onnx_dir = output_dir / args.onnx_subdir
        tokenizer_path = output_dir / args.tokenizer_name
        if onnx_dir.exists() and tokenizer_path.exists():
            print("Assets already present; use --force to re-download.")
            return 0

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

    print("PocketTTS assets downloaded.")
    print(f"  Models dir : {output_dir / args.onnx_subdir}")
    print(f"  Tokenizer  : {output_dir / args.tokenizer_name}")
    print(f"  Module path: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
