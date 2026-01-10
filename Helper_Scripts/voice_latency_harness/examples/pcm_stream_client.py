#!/usr/bin/env python3
"""
Example PCM streaming client for `/api/v1/audio/speech`.

Streams raw PCM16 bytes and writes to a .pcm file. If `sounddevice` is installed,
it will play audio in real time.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
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


async def _stream_pcm(url: str, headers: dict, payload: dict, out_path: str, rate: int, channels: int) -> None:
    print(f"Streaming PCM → {out_path} (rate={rate}, channels={channels})")
    with open(out_path, "wb") as fout:
        # Optional realtime playback
        try:
            import sounddevice as sd
            import numpy as np
            use_playback = True
        except Exception:
            use_playback = False

        async for chunk in http_client.astream_bytes(
            method="POST",
            url=url,
            headers=headers,
            json=payload,
            timeout=60.0,
        ):
            if not chunk:
                continue
            fout.write(chunk)
            if use_playback:
                arr = np.frombuffer(chunk, dtype=np.int16)
                sd.play(arr, samplerate=rate, blocking=False)

        if "sd" in locals():
            try:
                sd.stop()
            except Exception:
                pass


def main() -> None:
    ap = argparse.ArgumentParser(description="PCM streaming client example")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default=None)
    ap.add_argument("--text", default="Hello from TLDW")
    ap.add_argument("--outfile", default="out.pcm")
    ap.add_argument("--rate", type=int, default=24000, help="Sample rate")
    ap.add_argument("--channels", type=int, default=1, help="Channels")
    args = ap.parse_args()

    url = f"{args.base.rstrip('/')}/api/v1/audio/speech"
    headers = {"Accept": "application/octet-stream", "Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    headers["X-Request-Id"] = str(uuid.uuid4())

    payload = {
        "model": "tts-1",
        "input": args.text,
        "voice": "alloy",
        "response_format": "pcm",
        "stream": True,
    }

    _configure_local_egress(args.base)
    try:
        asyncio.run(_stream_pcm(url, headers, payload, args.outfile, args.rate, args.channels))
    finally:
        try:
            asyncio.run(http_client.shutdown_http_client())
        except Exception:
            pass

    print("Done.")


if __name__ == "__main__":
    main()
