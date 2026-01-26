#!/usr/bin/env python3
"""
WebSocket TTS realtime client example (for `/api/v1/audio/stream/tts/realtime`).

Sends JSON control frames and writes received audio bytes to a file.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Iterable


def _chunk_text(text: str, size: int) -> Iterable[str]:
    if size <= 0 or size >= len(text):
        yield text
        return
    for i in range(0, len(text), size):
        yield text[i : i + size]


async def run(
    base: str,
    token: str | None,
    text: str,
    outfile: str,
    provider: str,
    model: str,
    voice: str,
    fmt: str,
    auto_flush_ms: int,
    auto_flush_tokens: int,
    chunk_size: int,
    delay_ms: int,
    send_commit: bool,
    send_final: bool,
) -> None:
    try:
        import websockets  # type: ignore
    except Exception:
        print("Please `pip install websockets`", file=sys.stderr)
        sys.exit(2)

    url = base.rstrip("/") + "/api/v1/audio/stream/tts/realtime"
    headers = {"X-Request-Id": str(uuid.uuid4())}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with websockets.connect(url, extra_headers=headers, max_size=None) as ws:
        config = {
            "type": "config",
            "provider": provider,
            "model": model,
            "voice": voice,
            "format": fmt,
            "auto_flush_ms": auto_flush_ms,
            "auto_flush_tokens": auto_flush_tokens,
        }
        await ws.send(json.dumps(config))

        for chunk in _chunk_text(text, chunk_size):
            await ws.send(json.dumps({"type": "text", "delta": chunk}))
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000.0)

        if send_commit:
            await ws.send(json.dumps({"type": "commit"}))
        if send_final:
            await ws.send(json.dumps({"type": "final"}))

        print(f"Receiving audio -> {outfile}")
        with open(outfile, "wb") as f:
            try:
                while True:
                    msg = await ws.recv()
                    if isinstance(msg, (bytes, bytearray)):
                        await asyncio.to_thread(f.write, msg)
                        continue
                    try:
                        data = json.loads(msg)
                    except Exception:
                        continue
                    msg_type = data.get("type")
                    if msg_type == "ready":
                        print(f"Ready: {data}")
                    elif msg_type == "warning":
                        print(f"Warning: {data.get('message')}")
                    elif msg_type == "error":
                        print(f"Error: {data.get('message')}")
                        break
                    elif msg_type == "done":
                        break
            except (websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                pass


def main() -> None:
    ap = argparse.ArgumentParser(description="WS realtime TTS client example")
    ap.add_argument("--base", default="ws://127.0.0.1:8000")
    ap.add_argument("--token", default=None)
    ap.add_argument("--text", default="Hello from TLDW realtime TTS")
    ap.add_argument("--outfile", default="out_ws_tts_realtime.pcm")
    ap.add_argument("--provider", default="vibevoice_realtime")
    ap.add_argument("--model", default="vibevoice-realtime-0.5b")
    ap.add_argument("--voice", default="default")
    ap.add_argument("--format", default="pcm")
    ap.add_argument("--auto-flush-ms", type=int, default=600)
    ap.add_argument("--auto-flush-tokens", type=int, default=60)
    ap.add_argument("--chunk-size", type=int, default=24)
    ap.add_argument("--delay-ms", type=int, default=10)
    ap.add_argument("--no-commit", action="store_false", dest="send_commit")
    ap.add_argument("--no-final", action="store_false", dest="send_final")
    args = ap.parse_args()

    asyncio.run(
        run(
            base=args.base,
            token=args.token,
            text=args.text,
            outfile=args.outfile,
            provider=args.provider,
            model=args.model,
            voice=args.voice,
            fmt=args.format,
            auto_flush_ms=args.auto_flush_ms,
            auto_flush_tokens=args.auto_flush_tokens,
            chunk_size=args.chunk_size,
            delay_ms=args.delay_ms,
            send_commit=args.send_commit,
            send_final=args.send_final,
        )
    )


if __name__ == "__main__":
    main()
