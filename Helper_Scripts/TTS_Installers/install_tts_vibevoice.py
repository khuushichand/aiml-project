#!/usr/bin/env python3
"""
Install VibeVoice TTS assets and dependencies.

By default, installs deps and snapshots the 1.5B variant:
  microsoft/VibeVoice-1.5B

Usage:
  python Helper_Scripts/TTS_Installers/install_tts_vibevoice.py [--variant {1.5B,7B,7B-Q8}] [--force]

Environment flags:
- TLDW_SETUP_SKIP_PIP=1         # skip pip installs
- TLDW_SETUP_SKIP_DOWNLOADS=1   # skip model downloads
- TLDW_SETUP_FORCE_DOWNLOADS=1  # force re-downloads (or pass --force)
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="Install VibeVoice TTS assets and deps")
    ap.add_argument("--variant", choices=["1.5B", "7B", "7B-Q8"], default="1.5B")
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
    plan = InstallPlan(tts=[TTSInstall(engine="vibevoice", variants=[args.variant])])
    status = im.InstallationStatus(plan)

    try:
        im._install_backend_dependencies("tts", "vibevoice", status, errors)
    except im.PipInstallBlockedError as e:  # type: ignore[attr-defined]
        print(f"[vibevoice] Skipped pip installs: {e}")
    except Exception as e:
        print(f"ERROR installing VibeVoice dependencies: {e}", file=sys.stderr)
        errors.append(str(e))

    try:
        im._install_vibevoice([args.variant])
    except im.DownloadBlockedError as e:  # type: ignore[attr-defined]
        print(f"[vibevoice] Skipped model downloads: {e}")
    except Exception as e:
        print(f"ERROR downloading VibeVoice assets: {e}", file=sys.stderr)
        errors.append(str(e))

    if errors:
        status.fail("; ".join(errors))
        return 1
    status.complete()
    print(f"VibeVoice install completed. Variant: {args.variant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
