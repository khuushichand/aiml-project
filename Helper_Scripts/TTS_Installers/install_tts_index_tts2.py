#!/usr/bin/env python3
"""
Prepare IndexTTS2 local TTS environment.

This will:
- pip install common deps (torch, torchaudio, transformers, sentencepiece, safetensors)
- create checkpoints/index_tts2/ if missing and drop a README with expected files

Usage:
  python Helper_Scripts/TTS_Installers/install_tts_index_tts2.py

Note:
- The adapter expects local checkpoints and a config.yaml under checkpoints/index_tts2/.
- If the upstream pip package provides indextts, you can optionally install it and follow
  their model download instructions; otherwise, copy your trained/converted assets there.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def pip_install(pkgs: list[str]) -> None:
    if _skip_pip():
        raise RuntimeError("pip installs are disabled via TLDW_SETUP_SKIP_PIP")
    cmd = [sys.executable, "-m", "pip", "install", "-U"] + pkgs
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def _skip_pip() -> bool:
    flag = os.getenv("TLDW_SETUP_SKIP_PIP")
    return bool(flag and flag.strip().lower() in {"1", "true", "yes", "y", "on"})


README_CONTENT = """
IndexTTS2 Checkpoints Directory
===============================

Place the following files here (names may vary by release):

- config.yaml
- acoustic model weights (e.g., model.safetensors / .bin)
- codec weights
- optional: Qwen emotion model assets if using emotion guidance

Update tldw_Server_API/app/core/TTS/tts_providers_config.yaml to point at:

providers:
  index_tts:
    enabled: true
    model_dir: "checkpoints/index_tts2"
    cfg_path:  "checkpoints/index_tts2/config.yaml"

The adapter imports indextts.infer_v2.IndexTTS2. If not provided by your environment,
install the upstream package (when available) or put the engine code on PYTHONPATH.
""".strip()


def main() -> int:
    # Core deps per TTS-README
    try:
        pip_install([
            "torch>=2.2.0",
            "torchaudio>=2.2.0",
            "transformers>=4.41.0",
            "sentencepiece>=0.1.99",
            "safetensors>=0.4.0",
        ])
    except Exception as e:
        print(f"ERROR installing IndexTTS2 deps: {e}", file=sys.stderr)
        return 1

    ckpt_dir = Path("checkpoints/index_tts2")
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    readme = ckpt_dir / "README.txt"
    if not readme.exists():
        readme.write_text(README_CONTENT, encoding="utf-8")
    print(f"Prepared {ckpt_dir} (README written)")
    print("Copy your model files and config.yaml into this directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

