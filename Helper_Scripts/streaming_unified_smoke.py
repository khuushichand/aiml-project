#!/usr/bin/env python3
"""
Reusable smoke helper for unified streaming (SSE/WS).

This script exercises the unified streaming abstraction without needing the WebUI:

- Chat SSE:  POST /api/v1/chat/completions with stream=true
- Embeddings SSE:  GET /api/v1/embeddings/orchestrator/events (admin-only; skipped on 403)
- Audio WS:  WS /api/v1/audio/stream/transcribe

It is intended as a quick verification that:
- Unified SSE/WS streams are enabled (STREAMS_UNIFIED=1 on the server),
- DONE semantics are correct (single [DONE]),
- Heartbeats and basic lifecycle frames are present,
- No obvious error frames are returned in the happy path.

Usage (single-user, local):
    export SINGLE_USER_API_KEY=your-key
    STREAMS_UNIFIED=1 python -m uvicorn tldw_Server_API.app.main:app --reload
    python Helper_Scripts/streaming_unified_smoke.py \
        --base-url http://127.0.0.1:8000 \
        --api-key "$SINGLE_USER_API_KEY"

Notes:
- Requires `tldw_Server_API` on the PYTHONPATH and (optionally) `websockets` for the audio WS check.
- You can skip individual checks via flags (see --help).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote, urlparse


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


def _status_from_exc(exc: Exception) -> int:
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            return int(getattr(resp, "status_code", 0) or 0)
        except Exception:
            pass
    msg = str(exc)
    for token in msg.split():
        if token.isdigit() and len(token) == 3:
            try:
                return int(token)
            except Exception:
                continue
    return 0


async def _iter_sse_lines(byte_iter):
    buffer = b""
    async for chunk in byte_iter:
        if not chunk:
            continue
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            yield line.rstrip(b"\r").decode("utf-8", errors="replace")
    if buffer:
        yield buffer.decode("utf-8", errors="replace")


_ensure_repo_root()

try:
    from tldw_Server_API.app.core import http_client
except Exception:
    print("tldw_Server_API not available; run from the repo root or set PYTHONPATH.", file=sys.stderr)
    raise SystemExit(1) from None


def _headers(api_key: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    return headers


def _print_banner(msg: str) -> None:
    print("\n" + "=" * 80)
    print(msg)
    print("=" * 80)


async def smoke_chat_sse(base_url: str, api_key: Optional[str], model: str, timeout: float = 600.0) -> None:
    """
    Smoke-test Chat SSE streaming via unified streams.

    - Ensures response is text/event-stream.
    - Reads SSE data lines and verifies exactly one [DONE].
    """
    _print_banner("[chat] SSE smoke test (/api/v1/chat/completions)")
    url = base_url.rstrip("/") + "/api/v1/chat/completions"
    payload: Dict[str, Any] = {
        "model": model,
        "stream": True,
        "messages": [{"role": "user", "content": "Say hello and then stop."}],
    }
    headers = _headers(api_key)

    done_count = 0
    error_frames = 0
    total_data_lines = 0
    error_payloads: list[str] = []

    t0 = time.time()
    ttft_ms: Optional[float] = None

    try:
        byte_iter = http_client.astream_bytes(
            method="POST",
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        async for raw in _iter_sse_lines(byte_iter):
            if raw is None:
                continue
            line = str(raw).strip()
            if not line:
                continue
            if not line.startswith("data:"):
                # Ignore event/id/comment lines here
                continue

            total_data_lines += 1
            if ttft_ms is None:
                ttft_ms = (time.time() - t0) * 1000.0

            data = line[len("data:") :].strip()
            if data == "[DONE]":
                done_count += 1
                print("[chat] received [DONE]")
                break

            # Try parse as JSON; ignore non-JSON payloads for the smoke test
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "error" in parsed:
                error_frames += 1
                if len(error_payloads) < 3:
                    try:
                        error_payloads.append(json.dumps(parsed.get("error"), ensure_ascii=True))
                    except Exception:
                        error_payloads.append(str(parsed.get("error")))
    except Exception as exc:
        status = _status_from_exc(exc)
        if status:
            print(f"[chat] HTTP {status}")
        raise

    print(f"[chat] ttft_ms={ttft_ms:.1f} data_lines={total_data_lines} error_frames={error_frames} done_count={done_count}")
    if done_count != 1:
        raise RuntimeError(f"[chat] expected exactly one [DONE], saw {done_count}")
    if error_frames:
        detail = "; ".join(error_payloads) if error_payloads else "unknown error"
        raise RuntimeError(f"[chat] saw {error_frames} error frames in stream: {detail}")


async def smoke_embeddings_sse(base_url: str, api_key: Optional[str], timeout: float = 120.0) -> None:
    """
    Smoke-test embeddings orchestrator SSE:
    - Confirms event: summary appears with JSON payload.
    - Skips test if endpoint returns 403 (admin-only).
    """
    _print_banner("[embeddings] SSE smoke test (/api/v1/embeddings/orchestrator/events)")
    url = base_url.rstrip("/") + "/api/v1/embeddings/orchestrator/events"
    headers = _headers(api_key)

    saw_summary = False
    summary_payloads = 0

    try:
        byte_iter = http_client.astream_bytes(
            method="GET",
            url=url,
            headers=headers,
            timeout=timeout,
        )
        current_event: Optional[str] = None
        async for raw in _iter_sse_lines(byte_iter):
            if raw is None:
                continue
            line = str(raw).rstrip("\n")
            if not line:
                # blank delimiter; reset event if needed
                current_event = None
                continue
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue

            data = line[len("data:") :].strip()
            if current_event == "summary":
                try:
                    json.loads(data)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"[embeddings] summary event contained non-JSON data: {e}") from e
                saw_summary = True
                summary_payloads += 1
                print("[embeddings] saw summary payload")
                # A single payload is enough for smoke
                break
    except Exception as exc:
        status = _status_from_exc(exc)
        if status == 403:
            print("[embeddings] 403 Forbidden (likely admin-only). Skipping this check.")
            return
        if status:
            print(f"[embeddings] HTTP {status}")
        raise

    print(f"[embeddings] saw_summary={saw_summary} summary_payloads={summary_payloads}")
    if not saw_summary:
        raise RuntimeError("[embeddings] did not observe any event: summary frames")


def _build_ws_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if base.startswith("https://"):
        ws_base = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        ws_base = "ws://" + base[len("http://") :]
    else:
        ws_base = "ws://" + base
    return ws_base + path


def smoke_audio_ws(base_url: str, api_key: Optional[str], timeout: float = 20.0) -> None:
    """
    Smoke-test Audio WebSocket unified lifecycle:
    - Connects to /api/v1/audio/stream/transcribe with token.
    - Sends a minimal config message.
    - Confirms at least one ping frame OR a done frame in the allowed time.
    """
    _print_banner("[audio] WS smoke test (/api/v1/audio/stream/transcribe)")

    try:
        import websockets  # type: ignore
    except Exception:
        print("[audio] websockets package not installed; skipping audio WS smoke test.")
        print("         Install with: pip install websockets  (or 'pip install .[dev]')")
        return

    if not api_key:
        raise RuntimeError("[audio] API key is required for WS auth (token query parameter)")

    ws_url = _build_ws_url(base_url, f"/api/v1/audio/stream/transcribe?token={quote(api_key, safe='')}")
    print(f"[audio] connecting to {ws_url}")

    async def _run() -> Tuple[int, bool]:
        ping_count = 0
        saw_done = False

        async with websockets.connect(ws_url) as ws:  # type: ignore[attr-defined]
            config_msg = {
                "type": "config",
                "model": "parakeet",
                "language": "en",
                "enable_partial": False,
            }
            await ws.send(json.dumps(config_msg))
            print("[audio] sent config message")

            start = time.monotonic()
            while time.monotonic() - start < timeout:
                try:
                    raw = await ws.recv()
                except Exception as e:  # pragma: no cover - defensive
                    print(f"[audio] recv error: {e!r}")
                    break

                try:
                    msg = json.loads(raw)
                except Exception:
                    print("[audio] non-JSON frame:", repr(raw))
                    continue

                msg_type = msg.get("type")
                if msg_type == "ping":
                    ping_count += 1
                    print("[audio] ping frame")
                elif msg_type == "done":
                    saw_done = True
                    print("[audio] done frame")
                    break
                elif msg_type == "error":
                    print("[audio] error frame:", msg)
                    # For smoke, treat any error frame as a failure
                    raise RuntimeError(f"[audio] WS error frame received: {msg}")
                else:
                    # Domain payload (partial/transcription/full_transcript/etc.); ignore for smoke
                    print("[audio] domain frame:", msg_type)

        return ping_count, saw_done

    ping_count, saw_done = asyncio.run(_run())
    print(f"[audio] ping_count={ping_count} saw_done={saw_done}")
    if ping_count == 0 and not saw_done:
        raise RuntimeError("[audio] did not observe any ping or done frames; check WS handler / heartbeat config")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reusable smoke helper for unified streaming (Chat SSE, Embeddings SSE, Audio WS)."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("TLDW_BASE_URL", "http://127.0.0.1:8000"),
        help="Server base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("TLDW_API_KEY") or os.getenv("SINGLE_USER_API_KEY"),
        help="API key (X-API-KEY / token) for single-user or virtual-key auth.",
    )
    parser.add_argument(
        "--chat-model",
        default=os.getenv("TLDW_CHAT_MODEL", "openai/gpt-4o-mini"),
        help="Chat model name for /chat/completions (default: %(default)s).",
    )
    parser.add_argument(
        "--skip-chat",
        action="store_true",
        help="Skip Chat SSE smoke test.",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip Embeddings orchestrator SSE smoke test.",
    )
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Skip Audio WebSocket smoke test.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    base_url = args.base_url
    api_key = args.api_key
    chat_model = args.chat_model

    print(f"Base URL: {base_url}")
    print(f"API key present: {'yes' if api_key else 'no'}")
    print(f"Chat model: {chat_model}")
    print("Hints: ensure the server is running with STREAMS_UNIFIED=1 for unified streaming endpoints.\n")

    rc = 0
    try:
        _configure_local_egress(base_url)
        if not args.skip_chat:
            asyncio.run(smoke_chat_sse(base_url, api_key, chat_model))
            print("\n✅ Chat SSE smoke test passed.")
        else:
            print("\n[skip] Chat SSE smoke test skipped.")

        if not args.skip_embeddings:
            asyncio.run(smoke_embeddings_sse(base_url, api_key))
            print("\n✅ Embeddings SSE smoke test passed (or skipped if admin-only).")
        else:
            print("\n[skip] Embeddings SSE smoke test skipped.")

        if not args.skip_audio:
            smoke_audio_ws(base_url, api_key)
            print("\n✅ Audio WS smoke test passed (or skipped if websockets not installed).")
        else:
            print("\n[skip] Audio WS smoke test skipped.")

    except Exception as exc:
        print(f"\n❌ Unified streaming smoke helper failed: {exc}")
        rc = 1
    finally:
        try:
            asyncio.run(http_client.shutdown_http_client())
        except Exception:
            pass

    if rc == 0:
        print("\nAll selected unified streaming smoke checks completed successfully.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
