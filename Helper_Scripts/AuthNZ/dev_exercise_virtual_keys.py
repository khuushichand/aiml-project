#!/usr/bin/env python3
"""
Dev exercise: JWT virtual keys and X-API-KEY quotas end-to-end.

Requirements:
- Server running locally (default http://127.0.0.1:8000)
- An admin bearer token or single-user API key in environment.

Env:
- BASE_URL                              default http://127.0.0.1:8000
- ADMIN_BEARER_TOKEN                    for /api/v1/auth/virtual-key and user APIs (multi-user)
- X_API_KEY or SINGLE_USER_API_KEY      for single-user mode

What it does:
1) Mint a short-lived virtual JWT with max_calls=1 for chat.completions.
   - Call POST /api/v1/chat/completions twice: expect 200 then 403.
2) Mint a constrained virtual API key with max_calls=1 for chat.completions.
   - Call POST /api/v1/chat/completions twice with X-API-KEY: expect 200 then 403.
"""
import json
import os
import sys
import time
from typing import Dict, Any

try:
    import requests
except Exception:
    print("Please 'pip install requests' to run this helper.")
    sys.exit(1)


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_BEARER = os.getenv("ADMIN_BEARER_TOKEN")
API_KEY = os.getenv("X_API_KEY") or os.getenv("SINGLE_USER_API_KEY")


def _post(path: str, headers: Dict[str, str], json_body: Dict[str, Any]) -> requests.Response:
    url = f"{BASE_URL}{path}"
    return requests.post(url, headers=headers, json=json_body, timeout=30)


def _chat_payload() -> Dict[str, Any]:
    return {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Say hi"}]}
        ],
        "stream": False,
    }


def exercise_virtual_jwt():
    if not ADMIN_BEARER:
        print("[skip] ADMIN_BEARER_TOKEN not set; skipping JWT virtual key exercise.")
        return
    print("\n== JWT virtual key (max_calls=1) ==")
    headers = {"Authorization": f"Bearer {ADMIN_BEARER}"}
    body = {
        "scope": "workflows",
        "ttl_minutes": 10,
        "allowed_endpoints": ["chat.completions"],
        "allowed_methods": ["POST"],
        "allowed_paths": ["/api/v1/chat/completions"],
        "max_calls": 1,
    }
    r = _post("/api/v1/auth/virtual-key", headers, body)
    if r.status_code != 200:
        print(f"[warn] virtual-key mint failed: {r.status_code} {r.text}")
        return
    token = r.json().get("token")
    print("minted virtual JWT")
    chat_headers = {"Authorization": f"Bearer {token}"}
    r1 = _post("/api/v1/chat/completions", chat_headers, _chat_payload())
    print(f"call #1: {r1.status_code}")
    r2 = _post("/api/v1/chat/completions", chat_headers, _chat_payload())
    print(f"call #2: {r2.status_code} (expected 403)")


def exercise_virtual_api_key():
    if not ADMIN_BEARER:
        print("[skip] ADMIN_BEARER_TOKEN not set; skipping API key mint.")
        return
    print("\n== Virtual API key (max_calls=1) ==")
    headers = {"Authorization": f"Bearer {ADMIN_BEARER}"}
    # Self-service endpoint for current user
    body = {
        "name": "vk-demo",
        "allowed_endpoints": ["chat.completions"],
        "metadata": {"allowed_methods": ["POST"], "allowed_paths": ["/api/v1/chat/completions"], "max_calls": 1},
        "expires_in_days": 1,
    }
    url = f"{BASE_URL}/api/v1/users/api-keys/virtual"
    r = requests.post(url, headers=headers, json=body, timeout=30)
    if r.status_code != 200:
        print(f"[warn] virtual api key mint failed: {r.status_code} {r.text}")
        return
    key = r.json().get("key")
    print("minted virtual API key")
    chat_headers = {"X-API-KEY": key}
    r1 = _post("/api/v1/chat/completions", chat_headers, _chat_payload())
    print(f"call #1: {r1.status_code}")
    r2 = _post("/api/v1/chat/completions", chat_headers, _chat_payload())
    print(f"call #2: {r2.status_code} (expected 403)")


def exercise_single_user_key():
    if not API_KEY:
        print("[skip] SINGLE_USER_API_KEY not set; skipping single-user demo.")
        return
    print("\n== Single-user API key (baseline) ==")
    headers = {"X-API-KEY": API_KEY}
    r = _post("/api/v1/chat/completions", headers, _chat_payload())
    print(f"baseline call with X-API-KEY: {r.status_code}")


if __name__ == "__main__":
    print(f"Base URL: {BASE_URL}")
    exercise_single_user_key()
    exercise_virtual_jwt()
    exercise_virtual_api_key()
    print("\nDone.")
