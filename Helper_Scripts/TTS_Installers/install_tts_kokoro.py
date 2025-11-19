#!/usr/bin/env python3
"""
Install Kokoro TTS assets and dependencies.

Defaults (PyTorch-first, matching hexgrad/Kokoro-82M layout):
- PyTorch model: models/kokoro/kokoro-v1_0.pth
- Voices dir  : models/kokoro/voices/

Usage:
  # PyTorch (default; does not download the model checkpoint by default)
  python Helper_Scripts/TTS_Installers/install_tts_kokoro.py [--model-only|--voices-only] \
      [--model-path PATH] [--voices-dir PATH] [--force]

  # ONNX assets (optional)
  python Helper_Scripts/TTS_Installers/install_tts_kokoro.py --engine onnx \
      [--model-path PATH] [--voices-dir PATH] [--onnx-provider {auto,cpu,cuda}] [--force]

Environment flags respected (optional):
- TLDW_SETUP_SKIP_PIP=1         # skip pip installs
- TLDW_SETUP_SKIP_DOWNLOADS=1   # skip HF downloads
- TLDW_SETUP_FORCE_DOWNLOADS=1  # overwrite existing assets

This script:
1) Installs required pip packages for the kokoro adapter.
2) By default, prepares a PyTorch layout suitable for hexgrad/Kokoro-82M or similar
   (installs dependencies and voices; you still supply the .pth checkpoint unless
   you override --model-path in combination with a custom installer).
3) Optionally, when --engine onnx is specified, downloads the v1.0 ONNX model and
   voices directory from HF and configures ONNX Runtime wheels.
4) Detects eSpeak NG and prints platform guidance if not found.
"""
from __future__ import annotations

import argparse
import os
import sys
import platform
from pathlib import Path
from ctypes.util import find_library as _ctypes_find_library


def _set_onnx_runtime_override(onnx_provider: str | None) -> None:
    """
    Optionally override ONNX Runtime backend selection for this installer run.

    - onnx_provider == "cuda" forces GPU wheels (onnxruntime-gpu) where available.
    - onnx_provider == "cpu" forces CPU wheels even if CUDA is present.
    - onnx_provider == "auto" (default) leaves detection to the installer.

    The install_manager respects the following environment variables:
      - TLDW_SETUP_FORCE_GPU=1  -> prefer GPU packages
      - TLDW_SETUP_FORCE_CPU=1  -> force CPU-only packages
    """
    if not onnx_provider or onnx_provider == "auto":
        return

    # Clear any previous override in this process
    os.environ.pop("TLDW_SETUP_FORCE_GPU", None)
    os.environ.pop("TLDW_SETUP_FORCE_CPU", None)

    if onnx_provider == "cuda":
        os.environ["TLDW_SETUP_FORCE_GPU"] = "1"
    elif onnx_provider == "cpu":
        os.environ["TLDW_SETUP_FORCE_CPU"] = "1"


def _run_install(
    model_path: Path,
    voices_dir: Path,
    model_only: bool,
    voices_only: bool,
    onnx_provider: str | None = None,
    engine: str = "pytorch",
) -> int:
    # Defer heavy imports to runtime so the script can show friendly errors
    try:
        from tldw_Server_API.app.core.Setup import install_manager as im
        from tldw_Server_API.app.core.Setup.install_schema import InstallPlan, TTSInstall
    except Exception as e:
        print("ERROR: Unable to import internal installer utilities:", e, file=sys.stderr)
        print("Ensure you run from the repo root and that the project is installed (pip install -e .).", file=sys.stderr)
        return 2

    errors: list[str] = []

    variants: list[str] = []
    if engine == "onnx":
        # Optional: allow users to force CPU/GPU ONNX Runtime wheels for Kokoro.
        _set_onnx_runtime_override(onnx_provider)
        variants.extend(["onnx", "voices"])
    else:
        # PyTorch path: rely on generic kokoro dependencies and voices directory only.
        variants.append("voices")

    plan = InstallPlan(tts=[TTSInstall(engine="kokoro", variants=variants)])
    status = im.InstallationStatus(plan)

    # Step 1: dependencies
    try:
        im._install_backend_dependencies("tts", "kokoro", status, errors)
    except im.PipInstallBlockedError as e:  # type: ignore[attr-defined]
        print(f"[kokoro] Skipped pip installs: {e}")
    except Exception as e:
        print(f"ERROR installing kokoro dependencies: {e}", file=sys.stderr)
        errors.append(str(e))

    # Step 2: downloads / asset preparation
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    try:
        # Ensure destination directories exist
        model_path.parent.mkdir(parents=True, exist_ok=True)
        voices_dir.mkdir(parents=True, exist_ok=True)

        # If custom locations were provided, write them into config so the installer uses them
        default_model = Path("models/kokoro/kokoro-v1_0.pth" if engine != "onnx" else "models/kokoro/onnx/model.onnx")
        default_voices = Path("models/kokoro/voices")
        try:
            if model_path != default_model or voices_dir != default_voices:
                from tldw_Server_API.app.core.Setup import setup_manager as sm
                sm.update_config({
                    'TTS-Settings': {
                        'kokoro_model_path': str(model_path),
                        'kokoro_voices_json': str(voices_dir),
                    }
                })
        except Exception:
            # Non-fatal; fallback to defaults
            pass

        # Perform downloads / snapshotting
        im._install_kokoro(variants)
    except im.DownloadBlockedError as e:  # type: ignore[attr-defined]
        print(f"[kokoro] Skipped model downloads: {e}")
    except Exception as e:
        print(f"ERROR downloading Kokoro assets: {e}", file=sys.stderr)
        errors.append(str(e))

    # Step 3: eSpeak NG detection
    _check_espeak()

    if errors:
        status.fail("; ".join(errors))
        return 1
    status.complete()
    print("\nKokoro install completed.")
    print(f"Engine     : {engine}")
    print(f"Model path : {model_path}")
    print(f"Voices dir : {voices_dir}")
    return 0


def _check_espeak() -> None:
    path = _discover_espeak_library()
    if path:
        print(f"eSpeak NG detected: {path}")
        return
    print("\n[NOTICE] eSpeak NG library not detected. Kokoro ONNX can run without an explicit"
          " PHONEMIZER_ESPEAK_LIBRARY in most setups, but you need eSpeak NG installed.")
    sys_plat = sys.platform
    if sys_plat == "darwin":
        print("macOS install:   brew install espeak")
    elif sys_plat.startswith("linux"):
        print("Linux install:   sudo apt-get install espeak-ng  (Debian/Ubuntu)")
        print("                 sudo dnf install espeak-ng       (Fedora)")
        print("                 sudo pacman -S espeak-ng        (Arch)")
    elif sys_plat in ("win32", "cygwin"):
        print("Windows install: choco install espeak (or use the official installer)")
    else:
        print("Install eSpeak NG via your OS package manager.")


def _discover_espeak_library() -> str | None:
    # 1) Environment override
    env_path = os.getenv("PHONEMIZER_ESPEAK_LIBRARY")
    if env_path and os.path.exists(env_path):
        return env_path
    # 2) Platform heuristics
    sys_plat = sys.platform
    candidates: list[str] = []
    if sys_plat == "darwin":
        candidates = [
            "/opt/homebrew/lib/libespeak-ng.dylib",
            "/usr/local/lib/libespeak-ng.dylib",
            "/opt/local/lib/libespeak-ng.dylib",
        ]
    elif sys_plat.startswith("linux"):
        arch = platform.machine() or ""
        candidates = [
            f"/usr/lib/{arch}/libespeak-ng.so.1" if arch else "",
            "/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1",
            "/usr/lib/aarch64-linux-gnu/libespeak-ng.so.1",
            "/usr/lib64/libespeak-ng.so.1",
            "/usr/lib/libespeak-ng.so.1",
            "/lib/x86_64-linux-gnu/libespeak-ng.so.1",
            "/lib/aarch64-linux-gnu/libespeak-ng.so.1",
            "/lib/libespeak-ng.so.1",
        ]
    elif sys_plat in ("win32", "cygwin"):
        pf = os.environ.get("PROGRAMFILES", r"C:\\Program Files")
        pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)")
        candidates = [
            os.path.join(pf, "eSpeak NG", "libespeak-ng.dll"),
            os.path.join(pf86, "eSpeak NG", "libespeak-ng.dll"),
        ]
        for d in os.environ.get("PATH", "").split(os.pathsep):
            if d:
                candidates.append(os.path.join(d, "libespeak-ng.dll"))
    # 3) ctypes resolution may return a soname; only accept absolute paths
    lib = _ctypes_find_library("espeak-ng") or _ctypes_find_library("espeak")
    if lib and os.path.isabs(lib) and os.path.exists(lib):
        return lib
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Install Kokoro TTS assets and deps")
    ap.add_argument(
        "--engine",
        choices=["pytorch", "onnx"],
        default="pytorch",
        help="Which Kokoro backend to prepare: 'pytorch' (default) or 'onnx'.",
    )
    ap.add_argument(
        "--model-path",
        default=None,
        help=(
            "Destination path for Kokoro model (PyTorch or ONNX). "
            "Defaults: PyTorch -> models/kokoro/kokoro-v1_0.pth; "
            "ONNX -> models/kokoro/onnx/model.onnx."
        ),
    )
    ap.add_argument("--voices-dir", default="models/kokoro/voices", help="Destination directory for voices")
    ap.add_argument("--model-only", action="store_true", help="Only install model (skip voices)")
    ap.add_argument("--voices-only", action="store_true", help="Only install voices (skip model)")
    ap.add_argument(
        "--onnx-provider",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help=(
            "Select ONNX Runtime backend for Kokoro dependencies when --engine onnx "
            "is used: 'auto' (default) uses CUDA when detected, 'cpu' forces CPU "
            "wheels, and 'cuda' forces GPU wheels where available."
        ),
    )
    ap.add_argument("--force", action="store_true", help="Overwrite existing assets and force re-downloads")
    args = ap.parse_args()

    if args.model_only and args.voices_only:
        print("Choose only one of --model-only or --voices-only", file=sys.stderr)
        return 2

    if args.force:
        os.environ['TLDW_SETUP_FORCE_DOWNLOADS'] = '1'

    # Choose sensible defaults per engine when model_path not explicitly provided
    if args.model_path:
        model_path = Path(args.model_path)
    else:
        if args.engine == "onnx":
            model_path = Path("models/kokoro/onnx/model.onnx")
        else:
            model_path = Path("models/kokoro/kokoro-v1_0.pth")
    voices_dir = Path(args.voices_dir)
    return _run_install(
        model_path,
        voices_dir,
        args.model_only,
        args.voices_only,
        args.onnx_provider,
        engine=args.engine,
    )


if __name__ == "__main__":
    raise SystemExit(main())
