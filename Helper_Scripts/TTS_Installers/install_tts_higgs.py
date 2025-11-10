#!/usr/bin/env python3
"""
Install Higgs Audio V2 TTS assets and dependencies.

This will:
- pip install required packages (torch, torchaudio, boson_ai/higgs-audio via git, etc.)
- snapshot model repos (generation + tokenizer) via huggingface_hub

Usage:
  python Helper_Scripts/TTS_Installers/install_tts_higgs.py [--force]

Environment flags:
- TLDW_SETUP_SKIP_PIP=1         # skip pip installs
- TLDW_SETUP_SKIP_DOWNLOADS=1   # skip model downloads
- TLDW_SETUP_FORCE_DOWNLOADS=1  # force re-downloads (or pass --force)
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Install Higgs Audio V2 TTS assets and dependencies")
    ap.add_argument("--force", action="store_true", help="force re-downloads where applicable")
    args = ap.parse_args()

    try:
        from tldw_Server_API.app.core.Setup import install_manager as im
        from tldw_Server_API.app.core.Setup.install_schema import InstallPlan, TTSInstall
    except Exception as e:
        print("ERROR: Unable to import internal installer utilities:", e, file=sys.stderr)
        print("Run from the repo root and ensure 'pip install -e .' has been run.", file=sys.stderr)
        return 2

    if args.force:
        os.environ['TLDW_SETUP_FORCE_DOWNLOADS'] = '1'

    errors: list[str] = []
    plan = InstallPlan(tts=[TTSInstall(engine="higgs", variants=[])])
    status = im.InstallationStatus(plan)

    try:
        im._install_backend_dependencies("tts", "higgs", status, errors)
    except im.PipInstallBlockedError as e:  # type: ignore[attr-defined]
        print(f"[higgs] Skipped pip installs: {e}")
    except Exception as e:
        print(f"ERROR installing Higgs dependencies: {e}", file=sys.stderr)
        errors.append(str(e))

    try:
        im._install_higgs()
    except im.DownloadBlockedError as e:  # type: ignore[attr-defined]
        print(f"[higgs] Skipped model downloads: {e}")
    except Exception as e:
        print(f"ERROR downloading Higgs assets: {e}", file=sys.stderr)
        errors.append(str(e))

    if errors:
        status.fail("; ".join(errors))
        return 1
    status.complete()
    print("Higgs install completed. Models cached via HF hub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
