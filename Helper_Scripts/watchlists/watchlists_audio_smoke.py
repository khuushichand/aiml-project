#!/usr/bin/env python3
"""
Watchlists audio briefing smoke script.

Flow:
1) Create temporary source and job.
2) Trigger one run.
3) Create output with generate_audio=true.
4) Poll /watchlists/runs/{run_id}/audio for status/artifact metadata.
5) Optionally cleanup source/job.

This script validates API wiring and queueing. It does not require audio artifact
completion unless --require-download is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from typing import Any, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _env_first(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _build_headers(api_key: Optional[str], bearer: Optional[str]) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return str(raw)


def _trim(text: str, limit: int = 320) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _request_json(
    *,
    base_url: str,
    method: str,
    path: str,
    headers: dict[str, str],
    timeout: float,
    body: dict[str, Any] | None = None,
) -> Tuple[int, Any | None, str]:
    url = base_url.rstrip("/") + path
    req_headers = dict(headers)
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = Request(url, data=payload, method=method)
    for key, value in req_headers.items():
        req.add_header(key, value)

    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            status = int(resp.getcode())
            raw = _decode(resp.read() or b"")
    except HTTPError as exc:
        status = int(getattr(exc, "code", 0) or 0)
        raw = _decode(exc.read() or b"")
    except URLError as exc:
        return 0, None, f"URL error: {exc}"
    except Exception as exc:
        return 0, None, f"Request error: {exc}"

    parsed: Any | None = None
    if raw:
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
    return status, parsed, raw


def _best_effort_delete(
    *,
    base_url: str,
    headers: dict[str, str],
    timeout: float,
    path: str,
) -> None:
    status, _, raw = _request_json(
        base_url=base_url,
        method="DELETE",
        path=path,
        headers=headers,
        timeout=timeout,
    )
    if status in (200, 204, 404):
        return
    print(f"[WARN] cleanup failed {path}: status={status} body={_trim(raw)}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end watchlists audio briefing smoke flow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--base-url",
        default=_env_first("TLDW_BASE_URL", "BASE_URL") or "http://127.0.0.1:8000",
        help="API base URL",
    )
    parser.add_argument(
        "--api-key",
        default=_env_first("SINGLE_USER_API_KEY", "X_API_KEY", "TLDW_API_KEY"),
        help="Single-user API key",
    )
    parser.add_argument(
        "--bearer",
        default=_env_first("ADMIN_BEARER", "TLDW_BEARER", "TLDW_BEARER_TOKEN", "TLDW_TOKEN"),
        help="Bearer token for multi-user auth",
    )
    parser.add_argument(
        "--feed-url",
        default="https://www.state.gov/rss-feed/press-releases/feed/",
        help="RSS feed URL used for smoke source",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    parser.add_argument("--audio-poll-attempts", type=int, default=8, help="Polling attempts for /runs/{run_id}/audio")
    parser.add_argument("--audio-poll-interval", type=float, default=2.0, help="Seconds between audio polling attempts")
    parser.add_argument("--target-audio-minutes", type=int, default=5, help="Requested target audio minutes")
    parser.add_argument("--audio-model", default=None, help="Optional audio model override")
    parser.add_argument("--audio-voice", default=None, help="Optional audio voice override")
    parser.add_argument("--audio-speed", type=float, default=None, help="Optional audio speed override")
    parser.add_argument("--llm-provider", default=None, help="Optional LLM provider override for audio compose step")
    parser.add_argument("--llm-model", default=None, help="Optional LLM model override for audio compose step")
    parser.add_argument(
        "--require-download",
        action="store_true",
        help="Fail unless /runs/{run_id}/audio exposes a download_url by the end of polling",
    )
    parser.add_argument(
        "--keep-resources",
        action="store_true",
        help="Do not delete created source/job after run",
    )
    args = parser.parse_args(argv)

    headers = _build_headers(args.api_key, args.bearer)
    if not headers.get("X-API-KEY") and not headers.get("Authorization"):
        print("[WARN] No auth header configured; set --api-key/--bearer or env vars.")

    suffix = uuid.uuid4().hex[:10]
    source_id: int | None = None
    job_id: int | None = None

    try:
        source_payload = {
            "name": f"audio-smoke-source-{suffix}",
            "url": args.feed_url,
            "source_type": "rss",
            "tags": ["smoke", "audio"],
        }
        status, data, raw = _request_json(
            base_url=args.base_url,
            method="POST",
            path="/api/v1/watchlists/sources",
            headers=headers,
            timeout=args.timeout,
            body=source_payload,
        )
        if status != 200 or not isinstance(data, dict) or "id" not in data:
            print(f"[FAIL] create source: status={status} body={_trim(raw)}")
            return 1
        source_id = int(data["id"])
        print(f"[PASS] source created id={source_id}")

        job_payload = {
            "name": f"audio-smoke-job-{suffix}",
            "scope": {"sources": [source_id]},
            "schedule_expr": None,
            "timezone": "UTC",
            "active": True,
        }
        status, data, raw = _request_json(
            base_url=args.base_url,
            method="POST",
            path="/api/v1/watchlists/jobs",
            headers=headers,
            timeout=args.timeout,
            body=job_payload,
        )
        if status != 200 or not isinstance(data, dict) or "id" not in data:
            print(f"[FAIL] create job: status={status} body={_trim(raw)}")
            return 1
        job_id = int(data["id"])
        print(f"[PASS] job created id={job_id}")

        status, data, raw = _request_json(
            base_url=args.base_url,
            method="POST",
            path=f"/api/v1/watchlists/jobs/{job_id}/run",
            headers=headers,
            timeout=max(args.timeout, 90.0),
            body={},
        )
        if status != 200 or not isinstance(data, dict) or "id" not in data:
            print(f"[FAIL] trigger run: status={status} body={_trim(raw)}")
            return 1
        run_id = int(data["id"])
        run_status = data.get("status")
        print(f"[PASS] run triggered id={run_id} status={run_status}")

        output_payload: dict[str, Any] = {
            "run_id": run_id,
            "title": f"Audio Smoke Output {suffix}",
            "format": "md",
            "generate_audio": True,
            "target_audio_minutes": int(args.target_audio_minutes),
        }
        if args.audio_model:
            output_payload["audio_model"] = args.audio_model
        if args.audio_voice:
            output_payload["audio_voice"] = args.audio_voice
        if args.audio_speed is not None:
            output_payload["audio_speed"] = float(args.audio_speed)
        if args.llm_provider:
            output_payload["llm_provider"] = args.llm_provider
        if args.llm_model:
            output_payload["llm_model"] = args.llm_model

        status, data, raw = _request_json(
            base_url=args.base_url,
            method="POST",
            path="/api/v1/watchlists/outputs",
            headers=headers,
            timeout=max(args.timeout, 120.0),
            body=output_payload,
        )
        if status != 200 or not isinstance(data, dict):
            print(f"[FAIL] create output: status={status} body={_trim(raw)}")
            if "no_items_available" in raw:
                print(
                    "[HINT] No items were ingested from the feed. Try --feed-url with a different RSS feed or run in TEST_MODE."
                )
            return 1

        output_id = data.get("id")
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        audio_task_id = metadata.get("audio_briefing_task_id")
        if not audio_task_id:
            print(f"[FAIL] output created but no audio_briefing_task_id in metadata: output_id={output_id}")
            return 1
        print(f"[PASS] output created id={output_id} audio_task_id={audio_task_id}")

        status, run_data, raw = _request_json(
            base_url=args.base_url,
            method="GET",
            path=f"/api/v1/watchlists/runs/{run_id}",
            headers=headers,
            timeout=args.timeout,
        )
        if status == 200 and isinstance(run_data, dict):
            run_stats = run_data.get("stats") if isinstance(run_data.get("stats"), dict) else {}
            stats_task_id = run_stats.get("audio_briefing_task_id")
            if stats_task_id == audio_task_id:
                print("[PASS] run stats contain audio_briefing_task_id")
            else:
                print(
                    f"[WARN] run stats audio_briefing_task_id mismatch expected={audio_task_id} actual={stats_task_id}"
                )
        else:
            print(f"[WARN] unable to verify run stats: status={status} body={_trim(raw)}")

        final_audio_payload: dict[str, Any] | None = None
        for attempt in range(1, int(args.audio_poll_attempts) + 1):
            status, audio_data, raw = _request_json(
                base_url=args.base_url,
                method="GET",
                path=f"/api/v1/watchlists/runs/{run_id}/audio",
                headers=headers,
                timeout=args.timeout,
            )
            if status != 200 or not isinstance(audio_data, dict):
                print(f"[WARN] audio poll {attempt}/{args.audio_poll_attempts}: status={status} body={_trim(raw)}")
            else:
                poll_task = audio_data.get("task_id")
                poll_status = audio_data.get("status")
                download_url = audio_data.get("download_url")
                print(
                    f"[INFO] audio poll {attempt}/{args.audio_poll_attempts}: status={poll_status} task_id={poll_task} download_url={download_url}"
                )
                if poll_task and str(poll_task) != str(audio_task_id):
                    print(
                        f"[FAIL] audio endpoint returned mismatched task_id expected={audio_task_id} actual={poll_task}"
                    )
                    return 1
                final_audio_payload = audio_data
                if download_url:
                    break

            if attempt < int(args.audio_poll_attempts):
                time.sleep(float(args.audio_poll_interval))

        if final_audio_payload is None:
            print("[FAIL] no valid response from /runs/{run_id}/audio")
            return 1

        final_status = final_audio_payload.get("status")
        final_download = final_audio_payload.get("download_url")
        if args.require_download and not final_download:
            print(
                f"[FAIL] require-download set but no download_url (final status={final_status})"
            )
            return 1

        print(
            f"[PASS] smoke completed run_id={run_id} output_id={output_id} audio_status={final_status} download_url={final_download}"
        )
        return 0
    finally:
        if args.keep_resources:
            if source_id or job_id:
                print(f"[INFO] keep-resources enabled (source_id={source_id}, job_id={job_id})")
            return
        if job_id is not None:
            _best_effort_delete(
                base_url=args.base_url,
                headers=headers,
                timeout=args.timeout,
                path=f"/api/v1/watchlists/jobs/{job_id}",
            )
        if source_id is not None:
            _best_effort_delete(
                base_url=args.base_url,
                headers=headers,
                timeout=args.timeout,
                path=f"/api/v1/watchlists/sources/{source_id}",
            )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
