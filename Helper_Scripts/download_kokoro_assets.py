#!/usr/bin/env python3
import argparse
import os
import sys
from urllib.request import urlopen

"""
Download Kokoro ONNX model and voices.json.
Usage:
  python Helper_Scripts/download_kokoro_assets.py \
    --onnx-url <URL> --voices-url <URL> \
    --model-path tldw_Server_API/app/core/TTS/models/kokoro-v0_19.onnx \
    --voices-json tldw_Server_API/app/core/TTS/models/voices.json
"""

def download(url: str, dest: str, force: bool = False) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and not force:
        print(f"Skip existing: {dest}")
        return
    print(f"Downloading {url} -> {dest}")
    with urlopen(url) as r, open(dest, 'wb') as f:
        while True:
            chunk = r.read(8192)
            if not chunk:
                break
            f.write(chunk)
    print(f"Saved: {dest}")

def main():
    p = argparse.ArgumentParser(description="Download Kokoro ONNX model and voices.json")
    p.add_argument('--onnx-url', required=False)
    p.add_argument('--voices-url', required=False)
    p.add_argument('--model-path', required=True)
    p.add_argument('--voices-json', required=True)
    p.add_argument('--force', action='store_true')
    args = p.parse_args()

    if not args.onnx_url and not os.path.exists(args.model_path):
        print("--onnx-url is required if model file does not exist", file=sys.stderr)
        sys.exit(2)
    if not args.voices_url and not os.path.exists(args.voices_json):
        print("--voices-url is required if voices.json does not exist", file=sys.stderr)
        sys.exit(2)

    if args.onnx_url:
        download(args.onnx_url, args.model_path, force=args.force)
    if args.voices_url:
        download(args.voices_url, args.voices_json, force=args.force)

    print("Done.")

if __name__ == '__main__':
    main()
