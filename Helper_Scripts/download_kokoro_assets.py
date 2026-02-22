#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

"""
Kokoro asset downloader (updated for v1.0 ONNX).

Recommended: use the one‑command installer instead:
  python Helper_Scripts/TTS_Installers/install_tts_kokoro.py

This helper supports two modes:
1) Legacy direct URLs (v0.19 layout; downloads a single voices.json)
2) Hugging Face repo snapshot (v1.0 layout; downloads onnx/model.onnx + voices/ dir)

Usage (v1.0 recommended):
  python Helper_Scripts/download_kokoro_assets.py \
    --repo-id onnx-community/Kokoro-82M-v1.0-ONNX-timestamped \
    --model-path models/kokoro/onnx/model.onnx \
    --voices-dir models/kokoro/voices

Legacy (v0.19):
  python Helper_Scripts/download_kokoro_assets.py \
    --onnx-url <URL> --voices-url <URL> \
    --model-path models/kokoro/kokoro-v0_19.onnx \
    --voices-json models/kokoro/voices.json
"""


def _download_url(url: str, dest: Path, force: bool = False) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        print(f"Skip existing: {dest}")
        return
    print(f"Downloading {url} -> {dest}")
    try:
        with urlopen(url, timeout=60) as r, open(dest, "wb") as f:  # nosec B310
            while True:
                chunk = r.read(8192)
                if not chunk:
                    break
                f.write(chunk)
    except (HTTPError, URLError) as e:
        print(f"ERROR downloading {url}: {e}", file=sys.stderr)
        raise
    print(f"Saved: {dest}")


def _hf_download_file(repo_id: str, filename: str, dest: Path, force: bool = False) -> None:
    try:
        from huggingface_hub import hf_hub_download
    except Exception as e:
        raise RuntimeError("huggingface_hub is required for repo downloads. pip install huggingface-hub") from e
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        print(f"Skip existing: {dest}")
        return
    print(f"Fetching {repo_id}:{filename} -> {dest}")
    # Download into HF cache, then copy to exact destination path
    src_fp = hf_hub_download(repo_id=repo_id, filename=filename, force_download=force)  # nosec B615
    shutil.copy2(src_fp, dest)


def _hf_download_dir(repo_id: str, subdir: str, dest: Path, force: bool = False) -> None:
    try:
        from huggingface_hub import snapshot_download
    except Exception as e:
        raise RuntimeError("huggingface_hub is required for repo downloads. pip install huggingface-hub") from e
    print(f"Fetching directory {repo_id}:{subdir} -> {dest}")
    # Skip if present and not forcing
    if dest.exists() and any(dest.iterdir()) and not force:
        print(f"Skip existing dir: {dest}")
        return
    # Download snapshot into a temporary folder, then copy the requested subdir
    import tempfile
    with tempfile.TemporaryDirectory(prefix="kokoro_hf_") as _td:
        tmp_dir = Path(_td)
        # Restrict snapshot to the requested subdirectory only to avoid downloading large ONNX files
        snap = Path(snapshot_download(  # nosec B615
            repo_id=repo_id,
            local_dir=str(tmp_dir),
            allow_patterns=[f"{subdir}", f"{subdir}/*", f"{subdir}/**"],
            force_download=force,
        ))
        src = snap / subdir
        if not src.exists():
            raise FileNotFoundError(f"Subdirectory '{subdir}' not found in snapshot of {repo_id}")
        # Prepare destination directory
        if dest.exists() and force:
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Copy directory contents while tempdir is alive
        shutil.copytree(src, dest, dirs_exist_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Download Kokoro assets (v1.0 ONNX or legacy v0.19)")
    # New (v1.0) options
    p.add_argument("--repo-id", default="onnx-community/Kokoro-82M-v1.0-ONNX-timestamped", help="HF repo id to pull from")
    p.add_argument("--model-relpath", default="onnx/model.onnx", help="Relative model path within repo (v1.0)")
    p.add_argument("--model-path", default="models/kokoro/onnx/model.onnx", help="Destination model path")
    p.add_argument("--voices-subdir", default="voices", help="Voices subdirectory within repo (v1.0)")
    p.add_argument("--voices-dir", default="models/kokoro/voices", help="Destination voices directory (v1.0)")
    p.add_argument("--model-only", action="store_true", help="Only fetch the model (skip voices dir)")
    p.add_argument("--voices-only", action="store_true", help="Only fetch the voices dir (skip model)")
    # Legacy options
    p.add_argument("--onnx-url", required=False, help="Direct URL to ONNX file (legacy)")
    p.add_argument("--voices-url", required=False, help="Direct URL to voices.json (legacy)")
    p.add_argument("--voices-json", required=False, help="Destination file for voices.json (legacy)")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    # Prevent conflicting flags
    if args.model_only and args.voices_only:
        print("Choose only one of --model-only or --voices-only", file=sys.stderr)
        return 2

    # Legacy URL mode when any legacy flag is provided
    legacy_mode = bool(args.onnx_url or args.voices_url or args.voices_json)
    if legacy_mode:
        print("[DEPRECATION] v0.19 URL mode detected: consider using the v1.0 repo mode or the installer.")
        try:
            if args.onnx_url:
                _download_url(args.onnx_url, Path(args.model_path), force=args.force)
            if args.voices_url:
                if not args.voices_json:
                    print("--voices-json is required to save voices.json in legacy mode", file=sys.stderr)
                    return 2
                _download_url(args.voices_url, Path(args.voices_json), force=args.force)
        except Exception as e:
            print(f"ERROR: legacy download failed: {e}", file=sys.stderr)
            return 1
        else:
            print("Done (legacy mode).")
            return 0

    # v1.0 ONNX repo mode
    model_path = Path(args.model_path)
    voices_dir = Path(args.voices_dir)
    repo_id = str(args.repo_id)

    try:
        if not args.voices_only:
            _hf_download_file(repo_id, args.model_relpath, model_path, force=args.force)
        if not args.model_only:
            _hf_download_dir(repo_id, args.voices_subdir, voices_dir, force=args.force)
    except Exception as e:
        print(f"ERROR: failed to download from repo: {e}", file=sys.stderr)
        return 1

    print("Done (v1.0 repo mode).")
    print(f"  Model : {model_path}")
    print(f"  Voices: {voices_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
