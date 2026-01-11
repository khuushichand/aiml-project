#!/usr/bin/env python3
"""
Example PCM streaming client for `/api/v1/audio/speech`.

Streams raw PCM16 bytes and writes to a .pcm file. If `sounddevice` is installed,
it will play audio in real time.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from loguru import logger

_HELPERS_ROOT = Path(__file__).resolve()
for _parent in [_HELPERS_ROOT, *_HELPERS_ROOT.parents]:
    if _parent.name == "Helper_Scripts":
        _parent_str = str(_parent)
        if _parent_str not in sys.path:
            sys.path.insert(0, _parent_str)
        break

from common.repo_utils import configure_local_egress, ensure_repo_root

ensure_repo_root()

try:
    from tldw_Server_API.app.core import http_client
except ImportError as err:
    print("tldw_Server_API not available; run from the repo root or set PYTHONPATH.", file=sys.stderr)
    raise SystemExit(1) from err


async def _stream_pcm(url: str, headers: dict, payload: dict, out_path: str, rate: int, channels: int) -> None:
    print(f"Streaming PCM → {out_path} (rate={rate}, channels={channels})")
    with open(out_path, "wb") as fout:
        # Optional realtime playback
        playback_stream = None
        pending = b""
        try:
            import sounddevice as sd
            import numpy as np
            try:
                playback_stream = sd.OutputStream(samplerate=rate, channels=channels, dtype="int16")
                playback_stream.start()
                use_playback = True
            except Exception as exc:
                print(f"PCM playback disabled: {exc}")
                logger.warning("PCM playback disabled: {}", exc)
                use_playback = False
        except Exception as exc:
            print(f"sounddevice unavailable; skipping playback: {exc}")
            logger.info("sounddevice unavailable; skipping playback: {}", exc)
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
                pending += chunk
                frame_bytes = 2 * channels
                aligned_len = len(pending) - (len(pending) % frame_bytes)
                if aligned_len:
                    frame_data = pending[:aligned_len]
                    pending = pending[aligned_len:]
                    arr = np.frombuffer(frame_data, dtype=np.int16)
                    if channels > 1:
                        arr = arr.reshape(-1, channels)
                    try:
                        if playback_stream is not None:
                            playback_stream.write(arr)
                    except Exception as exc:
                        logger.warning("PCM playback write failed: {}", exc)
                        use_playback = False
                        if playback_stream is not None:
                            try:
                                playback_stream.stop()
                                playback_stream.close()
                            except Exception as close_exc:
                                logger.warning("PCM playback shutdown failed: {}", close_exc)
                            playback_stream = None

        if playback_stream is not None:
            try:
                playback_stream.stop()
                playback_stream.close()
            except Exception as exc:
                logger.warning("PCM playback shutdown failed: {}", exc)


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

    configure_local_egress(args.base)
    try:
        asyncio.run(_stream_pcm(url, headers, payload, args.outfile, args.rate, args.channels))
    finally:
        try:
            asyncio.run(http_client.shutdown_http_client())
        except Exception as exc:
            logger.exception("Error shutting down http client: {}", exc)

    print("Done.")


if __name__ == "__main__":
    main()
