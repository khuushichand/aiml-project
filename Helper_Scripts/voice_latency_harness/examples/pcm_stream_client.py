#!/usr/bin/env python3
"""
Example PCM streaming client for `/api/v1/audio/speech`.

Streams raw PCM16 bytes and writes to a .pcm file. If `sounddevice` is installed,
it will play audio in real time.
"""
from __future__ import annotations

import argparse
import sys
import uuid


def main() -> None:
    ap = argparse.ArgumentParser(description="PCM streaming client example")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default=None)
    ap.add_argument("--text", default="Hello from TLDW")
    ap.add_argument("--outfile", default="out.pcm")
    ap.add_argument("--rate", type=int, default=24000, help="Sample rate")
    ap.add_argument("--channels", type=int, default=1, help="Channels")
    args = ap.parse_args()

    try:
        import httpx
    except Exception:
        print("Please `pip install httpx`", file=sys.stderr)
        sys.exit(2)

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

    with httpx.stream("POST", url, headers=headers, json=payload, timeout=60.0) as r:
        r.raise_for_status()
        print(f"Streaming PCM → {args.outfile} (rate={args.rate}, channels={args.channels})")
        with open(args.outfile, "wb") as fout:
            # Optional realtime playback
            try:
                import sounddevice as sd
                import numpy as np
                use_playback = True
            except Exception:
                use_playback = False

            for chunk in r.iter_bytes():
                if not chunk:
                    continue
                fout.write(chunk)
                if use_playback:
                    arr = np.frombuffer(chunk, dtype=np.int16)
                    sd.play(arr, samplerate=args.rate, blocking=False)

            if "sd" in locals():
                try:
                    sd.stop()
                except Exception:
                    pass

    print("Done.")


if __name__ == "__main__":
    main()
