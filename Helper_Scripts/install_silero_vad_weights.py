"""
Install Silero VAD weights into the project's `models/` directory.

This script is explicit and minimal by design:
  - It NEVER downloads Python code or git repos.
  - It ONLY copies or downloads a single `.onnx` weights file.

Priority:
  1. If faster-whisper is installed and exposes `silero_vad_v6.onnx` in its assets,
     copy that file into `<repo_root>/models/silero_vad/` (or `--dest`).
  2. If faster-whisper is not available, and you pass `--url` (or set
     `SILERO_VAD_WEIGHTS_URL`), download that URL to the destination path.
     If neither `--url` nor `SILERO_VAD_WEIGHTS_URL` is provided, the script
     will not download anything and will exit with an error.

Examples:
    # Copy from faster-whisper assets (no network):
    python Helper_Scripts/install_silero_vad_weights.py

    # Explicitly download weights from a URL you control:
    python Helper_Scripts/install_silero_vad_weights.py \\
        --url https://example.com/path/to/silero_vad_v6.onnx \\
        --dest models/silero_vad
"""

import argparse
import os
import shutil
import sys
import urllib.request
from pathlib import Path
from urllib.error import URLError

DEFAULT_SILERO_VAD_URL = (
    "https://raw.githubusercontent.com/snakers4/silero-vad/refs/heads/"
    "master/src/silero_vad/data/silero_vad.onnx"
)


def find_repo_root(start: Path) -> Path:
    """Best-effort repo root detection.

    Walk up from `start` until a directory containing either pyproject.toml
    or .git is found. If none is found, return the original `start`.
    """
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return start


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install Silero VAD weights into models/. "
            "By default copies from faster-whisper assets; with --url it "
            "downloads ONLY the .onnx file you specify."
        ),
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Destination directory under repo root (default: models/silero_vad)",
    )
    env_url_default = os.environ.get("SILERO_VAD_WEIGHTS_URL")
    parser.add_argument(
        "--url",
        type=str,
        default=env_url_default if env_url_default else None,
        help=(
            "URL to a Silero VAD ONNX file. "
            "If faster-whisper assets are unavailable, this URL will be "
            "downloaded. Omit this (and leave SILERO_VAD_WEIGHTS_URL "
            "unset) to disable downloading entirely; you can pass the "
            "official Silero VAD ONNX asset URL or a mirror you control."
        ),
    )
    return parser.parse_args()


def _copy_from_faster_whisper(dest_dir: Path) -> bool:
    """Copy weights from faster-whisper assets if available.

    Returns True on success, False when faster-whisper is unavailable or
    its Silero VAD asset cannot be found.
    """
    try:
        from faster_whisper.utils import get_assets_path
    except ImportError:
        return False

    assets = Path(get_assets_path())
    src = assets / "silero_vad_v6.onnx"
    if not src.exists():
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    print(f"Copied Silero VAD weights from faster-whisper assets to {dest}")
    return True


def _download_weights(url: str, dest_dir: Path) -> None:
    """Download ONNX weights from the given URL into dest_dir (weights only)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "silero_vad_v6.onnx"
    print(f"Downloading Silero VAD weights from {url} -> {dest}")
    # User-provided URL; script does not guess or hard-code sources.
    urllib.request.urlretrieve(url, dest)  # noqa: S310
    print(f"Downloaded Silero VAD weights to {dest}")


def main() -> int:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__).resolve())
    default_dest_dir = repo_root / "models" / "silero_vad"
    dest_dir = (
        (repo_root / args.dest)
        if args.dest and not args.dest.is_absolute()
        else (args.dest or default_dest_dir)
    )
    dest_dir = dest_dir.resolve()
    # 1) Try faster-whisper assets first (no network)
    if _copy_from_faster_whisper(dest_dir):
        return 0

    # 2) Fallback: explicit URL provided by user
    if args.url:
        try:
            _download_weights(args.url, dest_dir)
        except (OSError, URLError) as err:
            print(
                f"Failed to download Silero VAD weights from {args.url}: {err}",
                file=sys.stderr,
            )
            return 1
        else:
            return 0

    # 3) Nothing to do
    print(
        "Silero VAD weights not installed: faster-whisper assets not found "
        "and no --url / SILERO_VAD_WEIGHTS_URL provided.",
        file=sys.stderr,
    )
    print(
        "Either install faster-whisper or rerun with --url pointing to a "
        "silero_vad_v6.onnx file you control.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
