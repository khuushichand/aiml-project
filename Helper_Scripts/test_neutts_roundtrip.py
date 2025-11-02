"""Minimal NeuTTS round-trip test against a running server.

Usage:
  python Helper_Scripts/test_neutts_roundtrip.py \
    --api-key $SINGLE_USER_API_KEY \
    --host http://127.0.0.1:8000 \
    --ref ref.wav \
    --ref-text "This is Dave speaking in this sample." \
    --text "My name is Dave, and I'm from London." \
    --model neutts-air \
    --format wav \
    --out out.wav

Note:
- Requires NeuTTS prerequisites installed on the server host.
- For streaming, set --stream and use a GGUF model (e.g., neutts-air-q8-gguf).
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--host", default="http://127.0.0.1:8000")
    ap.add_argument("--model", default="neutts-air")
    ap.add_argument("--text", required=True)
    ap.add_argument("--ref", required=True, help="Path to reference audio (wav/mp3)")
    ap.add_argument("--ref-text", required=True, help="Reference text matching the audio")
    ap.add_argument("--format", default="wav", choices=["wav","mp3","opus","flac","pcm"])
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--out", default="speech.wav")
    args = ap.parse_args()

    ref_path = Path(args.ref)
    if not ref_path.exists():
        print(f"Reference audio not found: {ref_path}", file=sys.stderr)
        sys.exit(1)

    voice_ref_b64 = base64.b64encode(ref_path.read_bytes()).decode()
    url = f"{args.host}/api/v1/audio/speech"
    payload = {
        "model": args.model,
        "input": args.text,
        "response_format": args.format,
        "stream": bool(args.stream),
        "voice_reference": voice_ref_b64,
        "extra_params": {
            "reference_text": args.ref_text
        }
    }

    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "Content-Type": "application/json",
    }

    if args.stream:
        # Stream bytes and save incrementally
        with requests.post(url, headers=headers, data=json.dumps(payload), stream=True) as r:
            r.raise_for_status()
            with open(args.out, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        print(f"Saved streamed audio to {args.out}")
    else:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        Path(args.out).write_bytes(r.content)
        print(f"Saved audio to {args.out}")


if __name__ == "__main__":
    main()
