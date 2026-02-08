#!/usr/bin/env python3
"""
End-to-end Voice Assistant example for tldw_server.

Flow:
1) (Optional) Create a user custom voice command
2) Run REST voice command turn and save returned audio
3) Run WebSocket voice text turn and save streamed audio

This script defines a user command via POST /api/v1/voice/commands.
The command action is controlled by:
  - --custom-action-type
  - --custom-tool-name / --custom-workflow-template / --custom-custom-action
  - --custom-system-prompt
  - --custom-action-config-json (optional merge/override)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    import websockets
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise SystemExit(
        "Missing dependency: websockets. Install with `python -m pip install websockets`."
    ) from exc


def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


def _rest_headers(token: str) -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
    }
    if _looks_like_jwt(token):
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["X-API-KEY"] = token
    return headers


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    body = None
    if payload is not None:
        json_body = json.dumps(payload)
        print(f"HTTP {method} {url} JSON body: {json_body}")
        body = json_body.encode("utf-8")
    req = Request(url=url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc

    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {url} returned non-JSON response") from exc


def _build_ws_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid base URL: {base_url}")
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    base_path = parsed.path.rstrip("/")
    return f"{ws_scheme}://{parsed.netloc}{base_path}/api/v1/voice/assistant"


def _ensure_custom_command(base_url: str, headers: dict[str, str], args: argparse.Namespace) -> str:
    list_url = (
        f"{base_url}/api/v1/voice/commands?"
        + urlencode({"include_system": "false", "include_disabled": "true"})
    )
    command_list = _http_json("GET", list_url, headers=headers)
    commands = command_list.get("commands", [])

    for cmd in commands:
        phrases = cmd.get("phrases") or []
        if cmd.get("name") == args.custom_command_name or args.custom_phrase in phrases:
            return cmd.get("id", "<existing-command>")

    create_url = f"{base_url}/api/v1/voice/commands"
    action_config = _build_action_config(args)
    payload = {
        "name": args.custom_command_name,
        "phrases": [args.custom_phrase],
        "action_type": args.custom_action_type,
        "action_config": action_config,
        "priority": 40,
        "enabled": True,
        "requires_confirmation": False,
        "description": "Created by voice_agent_full_example.py",
    }
    created = _http_json("POST", create_url, headers=headers, payload=payload)
    return created.get("id", "<new-command>")


async def _ws_send_json(ws, payload: dict[str, Any]) -> None:
    """
    Serialize and send a WebSocket JSON message.
    Prints the exact JSON string before sending.
    """
    json_body = json.dumps(payload)
    print(f"WS JSON body: {json_body}")
    await ws.send(json_body)


def _build_action_config(args: argparse.Namespace) -> dict[str, Any]:
    """
    Build action_config from CLI flags.
    """
    action_type = args.custom_action_type
    if action_type == "llm_chat":
        config: dict[str, Any] = {
            "system_prompt": args.custom_system_prompt,
        }
    elif action_type == "mcp_tool":
        config = {
            "tool_name": args.custom_tool_name,
            "extract_query": True,
        }
    elif action_type == "workflow":
        config = {
            "workflow_template": args.custom_workflow_template,
            "extract_query": True,
        }
    elif action_type == "custom":
        config = {
            "action": args.custom_custom_action,
        }
    else:
        raise ValueError(f"Unsupported custom action type: {action_type}")

    if args.custom_action_config_json:
        try:
            override = json.loads(args.custom_action_config_json)
        except json.JSONDecodeError as exc:
            raise ValueError("--custom-action-config-json must be valid JSON") from exc
        if not isinstance(override, dict):
            raise ValueError("--custom-action-config-json must decode to a JSON object")
        config.update(override)

    return config


def _run_rest_turn(base_url: str, headers: dict[str, str], args: argparse.Namespace) -> tuple[str | None, str]:
    url = f"{base_url}/api/v1/voice/command"
    payload = {
        "text": args.rest_text,
        "include_tts": True,
        "tts_provider": args.tts_provider,
        "tts_voice": args.tts_voice,
        "tts_format": args.tts_format,
    }
    result = _http_json("POST", url, headers=headers, payload=payload)

    output_audio_b64 = result.get("output_audio")
    if output_audio_b64:
        audio_bytes = base64.b64decode(output_audio_b64)
        Path(args.rest_audio_out).write_bytes(audio_bytes)
        audio_path = args.rest_audio_out
    else:
        audio_path = None

    response_text = (
        result.get("action_result", {}).get("response_text")
        or "<no response_text>"
    )
    return audio_path, response_text


async def _run_ws_turn(ws_url: str, token: str, args: argparse.Namespace) -> tuple[str | None, str]:
    tts_chunks: list[bytes] = []
    final_response_text = "<no action_result response_text>"

    async with websockets.connect(ws_url, max_size=None) as ws:
        await _ws_send_json(ws, {"type": "auth", "token": token})
        auth_msg = json.loads(await ws.recv())
        if auth_msg.get("type") != "auth_ok":
            raise RuntimeError(f"WebSocket auth failed: {auth_msg}")

        await _ws_send_json(
            ws,
            {
                "type": "config",
                "stt_model": args.stt_model,
                "sample_rate": args.sample_rate,
                "tts_provider": args.tts_provider,
                "tts_voice": args.tts_voice,
                "tts_format": args.tts_format,
            },
        )
        config_msg = json.loads(await ws.recv())
        if config_msg.get("type") != "config_ack":
            raise RuntimeError(f"WebSocket config failed: {config_msg}")

        await _ws_send_json(ws, {"type": "text", "text": args.ws_text})

        while True:
            msg = json.loads(await ws.recv())
            msg_type = msg.get("type")
            print(f"WS <- {msg_type}")

            if msg_type == "action_result":
                final_response_text = msg.get("response_text") or final_response_text
            elif msg_type == "tts_chunk":
                data = msg.get("data")
                if data:
                    tts_chunks.append(base64.b64decode(data))
            elif msg_type == "error":
                raise RuntimeError(f"WebSocket turn error: {msg}")
            elif msg_type == "state_change" and msg.get("state") == "idle":
                break

    if tts_chunks:
        audio_bytes = b"".join(tts_chunks)
        Path(args.ws_audio_out).write_bytes(audio_bytes)
        return args.ws_audio_out, final_response_text
    return None, final_response_text


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a full Voice Assistant example flow")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Server base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="API key or JWT (default: VOICE_TOKEN or SINGLE_USER_API_KEY env var)",
    )
    parser.add_argument(
        "--ws-url",
        default=None,
        help="Optional full WebSocket URL override",
    )
    parser.add_argument(
        "--skip-command-create",
        action="store_true",
        help="Skip creating/checking a custom command",
    )
    parser.add_argument(
        "--custom-command-name",
        default="Example Status Command",
        help="Name for the user custom command",
    )
    parser.add_argument(
        "--custom-phrase",
        default="status report now",
        help="Trigger phrase for the user custom command",
    )
    parser.add_argument(
        "--custom-action-type",
        default="llm_chat",
        choices=["llm_chat", "mcp_tool", "workflow", "custom"],
        help="Action type for the custom command",
    )
    parser.add_argument(
        "--custom-system-prompt",
        default="You are a concise status assistant. Keep replies short and factual.",
        help="system_prompt for llm_chat action type",
    )
    parser.add_argument(
        "--custom-tool-name",
        default="media.search",
        help="tool_name for mcp_tool action type",
    )
    parser.add_argument(
        "--custom-workflow-template",
        default="search_and_summarize",
        help="workflow_template for workflow action type",
    )
    parser.add_argument(
        "--custom-custom-action",
        default="help",
        help="action for custom action type",
    )
    parser.add_argument(
        "--custom-action-config-json",
        default=None,
        help="Optional JSON object merged into action_config",
    )
    parser.add_argument(
        "--rest-text",
        default="help",
        help="Text for REST /voice/command call",
    )
    parser.add_argument(
        "--ws-text",
        default="show commands",
        help="Text for WebSocket text turn",
    )
    parser.add_argument(
        "--tts-provider",
        default="kokoro",
        help="TTS provider for both REST and WS turns",
    )
    parser.add_argument(
        "--tts-voice",
        default="af_heart",
        help="TTS voice for both REST and WS turns",
    )
    parser.add_argument(
        "--tts-format",
        default="mp3",
        choices=["mp3", "opus", "wav", "pcm"],
        help="Output audio format",
    )
    parser.add_argument(
        "--stt-model",
        default="parakeet",
        help="STT model for WS config",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Sample rate for WS config",
    )
    parser.add_argument(
        "--rest-audio-out",
        default="voice_rest_example.mp3",
        help="Output path for REST returned audio",
    )
    parser.add_argument(
        "--ws-audio-out",
        default="voice_ws_example.mp3",
        help="Output path for WS streamed audio",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    token = args.token or os.environ.get("VOICE_TOKEN") or os.environ.get("SINGLE_USER_API_KEY")
    if not token:
        print("Error: provide --token or set VOICE_TOKEN / SINGLE_USER_API_KEY", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    ws_url = args.ws_url or _build_ws_url(base_url)
    headers = _rest_headers(token)

    print(f"Base URL: {base_url}")
    print(f"WS URL:   {ws_url}")

    if not args.skip_command_create:
        print("Step 1/3: Ensuring custom command exists...")
        action_config = _build_action_config(args)
        print(f"  Command action_type:  {args.custom_action_type}")
        print(f"  Command action_config:{json.dumps(action_config, ensure_ascii=True)}")
        cmd_id = _ensure_custom_command(base_url, headers, args)
        print(f"  Custom command ready: {cmd_id}")
    else:
        print("Step 1/3: Skipped custom command creation.")

    print("Step 2/3: Running REST voice command turn...")
    rest_audio_path, rest_response = _run_rest_turn(base_url, headers, args)
    print(f"  REST response text: {rest_response}")
    if rest_audio_path:
        print(f"  REST audio saved:   {rest_audio_path}")
    else:
        print("  REST audio missing (check TTS config/provider).")

    print("Step 3/3: Running WebSocket voice text turn...")
    ws_audio_path, ws_response = asyncio.run(_run_ws_turn(ws_url, token, args))
    print(f"  WS response text:   {ws_response}")
    if ws_audio_path:
        print(f"  WS audio saved:     {ws_audio_path}")
    else:
        print("  WS audio missing (check TTS config/provider).")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
