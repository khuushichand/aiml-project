#!/usr/bin/env python3
"""
Install Dia TTS assets and dependencies.

This will:
- pip install required packages (torch, transformers, accelerate, etc.)
- snapshot the model repo (nari-labs/dia) via huggingface_hub

Usage:
  python Helper_Scripts/TTS_Installers/install_tts_dia.py

Environment flags:
- TLDW_SETUP_SKIP_PIP=1         # skip pip installs
- TLDW_SETUP_SKIP_DOWNLOADS=1   # skip model downloads
"""
from __future__ import annotations

import sys


def main() -> int:
    try:
        from tldw_Server_API.app.core.Setup import install_manager as im
        from tldw_Server_API.app.core.Setup.install_schema import InstallPlan, TTSInstall
    except Exception as e:
        print("ERROR: Unable to import internal installer utilities:", e, file=sys.stderr)
        print("Run from the repo root and ensure 'pip install -e .' has been run.", file=sys.stderr)
        return 2

    errors: list[str] = []
    plan = InstallPlan(tts=[TTSInstall(engine="dia", variants=[])])
    status = im.InstallationStatus(plan)

    try:
        im._install_backend_dependencies("tts", "dia", status, errors)
    except im.PipInstallBlockedError as e:  # type: ignore[attr-defined]
        print(f"[dia] Skipped pip installs: {e}")
    except Exception as e:
        print(f"ERROR installing Dia dependencies: {e}", file=sys.stderr)
        errors.append(str(e))

    try:
        im._install_dia()
    except im.DownloadBlockedError as e:  # type: ignore[attr-defined]
        print(f"[dia] Skipped model downloads: {e}")
    except Exception as e:
        print(f"ERROR downloading Dia assets: {e}", file=sys.stderr)
        errors.append(str(e))

    if errors:
        status.fail("; ".join(errors))
        return 1
    status.complete()
    print("Dia install completed. Model cached via HF hub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

