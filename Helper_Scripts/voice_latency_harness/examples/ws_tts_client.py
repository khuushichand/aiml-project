#!/usr/bin/env python3
"""
WebSocket TTS client example (for optional `/api/v1/audio/stream/tts`).

Sends a prompt frame and writes received PCM16 frames to a file.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid


async def run(base: str, token: str | None, text: str, outfile: str) -> None:
    try:
        import websockets  # type: ignore
    except Exception:
        print("Please `pip install websockets`", file=sys.stderr)
        sys.exit(2)

    url = base.rstrip("/") + "/api/v1/audio/stream/tts"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["X-Request-Id"] = str(uuid.uuid4())

    async with websockets.connect(url, extra_headers=headers, max_size=None) as ws:
        # Send prompt frame
        await ws.send(json.dumps({"type": "prompt", "text": text, "format": "pcm"}))
        print(f"Receiving PCM → {outfile}")
        with open(outfile, "wb") as f:
            try:
                while True:
                    msg = await ws.recv()
                    if isinstance(msg, (bytes, bytearray)):
                        f.write(msg)
                    else:
                        try:
                            data = json.loads(msg)
                            if data.get("type") == "error":
                                print(f"Server error: {data.get('message')}")
                                break
                        except Exception:
                            # Ignore non-JSON text
                            _ = None
            except (websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                _ = None


def main() -> None:
    ap = argparse.ArgumentParser(description="WS TTS client example")
    ap.add_argument("--base", default="ws://127.0.0.1:8000")
    ap.add_argument("--token", default=None)
    ap.add_argument("--text", default="Hello from TLDW")
    ap.add_argument("--outfile", default="out_ws_tts.pcm")
    args = ap.parse_args()
    asyncio.run(run(args.base, args.token, args.text, args.outfile))


if __name__ == "__main__":
    main()
