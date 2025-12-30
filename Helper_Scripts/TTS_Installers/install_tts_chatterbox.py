#!/usr/bin/env python3
"""
Install Chatterbox TTS dependencies (vendored integration helper).

Usage:
  python Helper_Scripts/TTS_Installers/install_tts_chatterbox.py [--with-lang]

This is a thin wrapper over Helper_Scripts/install_chatterbox_deps.py.
"""
from __future__ import annotations

import argparse
import runpy
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="Install Chatterbox TTS dependencies")
    ap.add_argument("--with-lang", action="store_true", help="install optional multilingual extras")
    args = ap.parse_args()

    # Forward args to the underlying helper by modifying sys.argv
    argv = [sys.argv[0]]
    if args.with_lang:
        argv.append("--with-lang")
    sys.argv = argv
    runpy.run_path("Helper_Scripts/install_chatterbox_deps.py", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
