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
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse


def _ensure_repo_root() -> None:
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "tldw_Server_API").is_dir():
            sys.path.insert(0, str(parent))
            return


def _configure_local_egress(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        return
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "0.0.0.0"} or host.startswith("127.") or host == "::1":
        os.environ.setdefault("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "false")
        if "WORKFLOWS_EGRESS_ALLOWED_PORTS" not in os.environ:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            os.environ["WORKFLOWS_EGRESS_ALLOWED_PORTS"] = f"{port},80,443"


_ensure_repo_root()

try:
    from tldw_Server_API.app.core import http_client
except Exception:
    print("tldw_Server_API not available; run from the repo root or set PYTHONPATH.", file=sys.stderr)
    raise SystemExit(1)


async def _stream_audio(url: str, headers: dict, payload: dict, out_path: Path) -> None:
    with out_path.open("ab") as fout:
        async for chunk in http_client.astream_bytes(
            method="POST",
            url=url,
            headers=headers,
            data=json.dumps(payload),
            timeout=60.0,
        ):
            if not chunk:
                continue
            fout.write(chunk)


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

    _configure_local_egress(args.host)

    try:
        if args.stream:
            # Stream bytes and save incrementally
            out_path = Path(args.out)
            if out_path.exists():
                out_path.unlink()
            asyncio.run(_stream_audio(url, headers, payload, out_path))
            print(f"Saved streamed audio to {args.out}")
        else:
            r = http_client.fetch(method="POST", url=url, headers=headers, json=payload, timeout=60.0)
            r.raise_for_status()
            Path(args.out).write_bytes(r.content)
            print(f"Saved audio to {args.out}")
    finally:
        try:
            asyncio.run(http_client.shutdown_http_client())
        except Exception:
            pass


if __name__ == "__main__":
    main()
