#!/usr/bin/env python3
"""
Install NeuTTS Air dependencies and optionally prefetch model assets.

This will:
- pip install required packages: neucodec, librosa, phonemizer, transformers, torch
- optional: install llama-cpp-python (for GGUF streaming) and onnxruntime
- optional: prefetch HF repos (backbone + codec) into local cache

Usage:
  python Helper_Scripts/TTS_Installers/install_tts_neutts.py [--prefetch] [--force] \
      [--backbone neuphonic/neutts-air|<local path>|<gguf repo>] \
      [--codec neuphonic/neucodec|neuphonic/distill-neucodec|neuphonic/neucodec-onnx-decoder]

Environment flags:
- TLDW_SETUP_SKIP_PIP=1         # skip pip installs
- TLDW_SETUP_SKIP_DOWNLOADS=1   # skip HF downloads
- TLDW_SETUP_FORCE_DOWNLOADS=1  # force re-downloads (or pass --force)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


DEFAULT_BACKBONE = "neuphonic/neutts-air"
DEFAULT_CODEC = "neuphonic/neucodec"


def pip_install(pkgs: list[str]) -> None:
    if _skip_pip():
        raise RuntimeError("pip installs are disabled via TLDW_SETUP_SKIP_PIP")
    cmd = [sys.executable, "-m", "pip", "install", "-U"] + pkgs
    idx = os.getenv('TLDW_SETUP_PIP_INDEX_URL')
    if idx:
        cmd.extend(['--index-url', idx])
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def _skip_pip() -> bool:
    flag = os.getenv("TLDW_SETUP_SKIP_PIP")
    return bool(flag and flag.strip().lower() in {"1", "true", "yes", "y", "on"})


def _skip_downloads() -> bool:
    flag = os.getenv("TLDW_SETUP_SKIP_DOWNLOADS")
    return bool(flag and flag.strip().lower() in {"1", "true", "yes", "y", "on"})


def _force_downloads() -> bool:
    flag = os.getenv("TLDW_SETUP_FORCE_DOWNLOADS")
    return bool(flag and flag.strip().lower() not in {"0", "false", "no", "off"})


def prefetch(backbone: str, codec: str) -> None:
    if _skip_downloads():
        print("[neutts] Skipping downloads: TLDW_SETUP_SKIP_DOWNLOADS=1")
        return
    try:
        from huggingface_hub import snapshot_download
    except Exception as e:
        # Try to install huggingface_hub (unless installs are disabled)
        if _skip_pip():
            print("[neutts] Cannot auto-install huggingface_hub due to TLDW_SETUP_SKIP_PIP=1; skipping downloads.")
            return
        print("Installing huggingface_hub to enable downloads...")
        pip_install(["huggingface_hub>=0.23.0"])
        from huggingface_hub import snapshot_download  # type: ignore

    def snap(repo: str) -> None:
        if os.path.isdir(repo):
            print(f"[neutts] Local path provided, skipping download: {repo}")
            return
        print(f"[neutts] Prefetching {repo} ...")
        # Prefetch into HF cache; no local_dir needed and no symlink flag
        snapshot_download(repo_id=repo, force_download=_force_downloads())

    snap(backbone)
    if codec:
        snap(codec)


def main() -> int:
    ap = argparse.ArgumentParser(description="Install NeuTTS Air dependencies and optionally prefetch models")
    ap.add_argument("--prefetch", action="store_true", help="download backbone/codec to local HF cache")
    ap.add_argument("--backbone", default=DEFAULT_BACKBONE, help="HF repo id or local path for backbone")
    ap.add_argument("--codec", default=DEFAULT_CODEC, help="HF repo id for codec (or onnx decoder)")
    ap.add_argument("--with-gguf", action="store_true", help="also install llama-cpp-python for GGUF streaming")
    ap.add_argument("--with-onnx", action="store_true", help="also install onnxruntime for ONNX decoder codec")
    ap.add_argument("--force", action="store_true", help="force re-downloads where applicable")
    args = ap.parse_args()

    # Core deps
    try:
        pip_install([
            "torch>=2.2.0",
            "phonemizer>=3.2.1",
            "librosa>=0.10.0",
            "transformers>=4.41.0",
            "neucodec>=0.0.4",
        ])
    except Exception as e:
        print(f"ERROR installing NeuTTS deps: {e}", file=sys.stderr)
        return 1

    # Optional extras
    opt_pkgs: list[str] = []
    if args.with_gguf:
        opt_pkgs.append("llama-cpp-python>=0.2.90")
    if args.with_onnx:
        opt_pkgs.append("onnxruntime>=1.16.0")
    if opt_pkgs:
        try:
            pip_install(opt_pkgs)
        except Exception as e:
            print(f"WARNING: Optional NeuTTS extras failed to install: {e}")

    if args.force:
        os.environ['TLDW_SETUP_FORCE_DOWNLOADS'] = '1'

    if args.prefetch:
        try:
            prefetch(args.backbone, args.codec)
        except Exception as e:
            print(f"WARNING: Prefetch failed: {e}")

    print("NeuTTS install completed.")
    print("- Configure in tts_providers_config.yaml under providers.neutts")
    print("- For streaming, use a GGUF backbone and run with --with-gguf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
