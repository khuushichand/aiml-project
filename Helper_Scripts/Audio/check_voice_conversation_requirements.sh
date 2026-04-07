#!/usr/bin/env bash
# Verify the backend-side gates the Playground uses for speech-to-speech.
#
# This script mirrors the client logic in:
# - apps/packages/ui/src/services/tldw/server-capabilities.ts
# - apps/packages/ui/src/hooks/useTldwAudioStatus.tsx
# - apps/packages/ui/src/services/tldw/voice-conversation.ts
#
# It prints PASS/FAIL for the effective server-side gates and includes
# diagnostics for the OpenAPI/docs-info inputs that produce those gates.

set -euo pipefail

SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"

BASE_URL="http://127.0.0.1:8000"
API_KEY="${SINGLE_USER_API_KEY:-}"
BEARER_TOKEN=""
TTS_PROVIDER=""
TIMEOUT_SECONDS="10"

usage() {
  cat <<EOF
Usage:
  $SCRIPT_NAME [options]

Options:
  --base-url URL         Server base URL. Default: $BASE_URL
  --api-key KEY          X-API-KEY to use for authenticated health probes.
  --bearer-token TOKEN   Bearer token to use for authenticated health probes.
  --tts-provider NAME    Optional provider key to validate in TTS health.
  --timeout SECONDS      Curl timeout in seconds. Default: $TIMEOUT_SECONDS
  -h, --help             Show this help.

Examples:
  $SCRIPT_NAME
  $SCRIPT_NAME --base-url http://127.0.0.1:8000 --api-key "\$SINGLE_USER_API_KEY"
  $SCRIPT_NAME --base-url https://server.example.com --bearer-token "<jwt>" --tts-provider openai
EOF
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Error: required command not found: $command_name" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --api-key)
      API_KEY="${2:-}"
      shift 2
      ;;
    --bearer-token)
      BEARER_TOKEN="${2:-}"
      shift 2
      ;;
    --tts-provider)
      TTS_PROVIDER="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      echo >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -n "$API_KEY" && -n "$BEARER_TOKEN" ]]; then
  echo "Error: pass either --api-key or --bearer-token, not both." >&2
  exit 1
fi

require_command curl
require_command python3

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fetch_json() {
  local name="$1"
  local url="$2"
  local auth_mode="${3:-none}"
  local body_file="$TMP_DIR/${name}.body"
  local meta_file="$TMP_DIR/${name}.meta"
  local err_file="$TMP_DIR/${name}.err"
  local -a curl_args=(
    -sS
    -L
    --connect-timeout "$TIMEOUT_SECONDS"
    --max-time "$TIMEOUT_SECONDS"
    -H "Accept: application/json"
  )

  if [[ "$auth_mode" == "auth" ]]; then
    if [[ -n "$API_KEY" ]]; then
      curl_args+=(-H "X-API-KEY: $API_KEY")
    elif [[ -n "$BEARER_TOKEN" ]]; then
      curl_args+=(-H "Authorization: Bearer $BEARER_TOKEN")
    fi
  fi

  : >"$body_file"
  : >"$err_file"

  local status="000"
  local curl_exit_code="0"
  set +e
  status="$(
    curl "${curl_args[@]}" \
      -o "$body_file" \
      -w "%{http_code}" \
      "$url" \
      2>"$err_file"
  )"
  curl_exit_code="$?"
  set -e

  printf 'status=%s\ncurl_exit_code=%s\nurl=%s\nauth_mode=%s\n' \
    "$status" \
    "$curl_exit_code" \
    "$url" \
    "$auth_mode" \
    >"$meta_file"
}

fetch_json "docs_info" "${BASE_URL%/}/api/v1/config/docs-info" "none"
fetch_json "openapi" "${BASE_URL%/}/openapi.json" "none"
fetch_json "stt_health" "${BASE_URL%/}/api/v1/audio/transcriptions/health" "auth"
fetch_json "tts_health" "${BASE_URL%/}/api/v1/audio/health" "auth"

python3 - "$TMP_DIR" "$TTS_PROVIDER" <<'PY'
import json
import sys
from pathlib import Path

tmp_dir = Path(sys.argv[1])
provider_hint = (sys.argv[2] if len(sys.argv) > 2 else "").strip().lower()

READY_TTS_STATUSES = {"enabled", "available", "ready", "healthy", "ok"}
AUDIO_CHAT_STREAM_PATH = "/api/v1/audio/chat/stream"


def read_meta(name):
    meta = {}
    meta_path = tmp_dir / f"{name}.meta"
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        meta[key] = value
    return meta


def load_response(name):
    meta = read_meta(name)
    status_raw = meta.get("status", "000").strip()
    exit_code_raw = meta.get("curl_exit_code", "0").strip()
    body = (tmp_dir / f"{name}.body").read_text(encoding="utf-8", errors="replace")
    try:
        parsed = json.loads(body) if body.strip() else None
        valid_json = True
    except json.JSONDecodeError:
        parsed = None
        valid_json = False
    try:
        status = int(status_raw)
    except ValueError:
        status = 0
    try:
        exit_code = int(exit_code_raw)
    except ValueError:
        exit_code = 0
    return status, exit_code, body, parsed, valid_json


def parse_booleanish(raw):
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return raw != 0
    if not isinstance(raw, str):
        return None
    normalized = raw.strip().lower()
    if not normalized:
        return None
    if normalized in {"true", "1", "yes", "on", "enabled"}:
        return True
    if normalized in {"false", "0", "no", "off", "disabled"}:
        return False
    return None


def extract_feature_flag(docs_info, key):
    if not isinstance(docs_info, dict):
      return None
    for map_key in ("capabilities", "supported_features"):
        payload = docs_info.get(map_key)
        if not isinstance(payload, dict) or key not in payload:
            continue
        parsed = parse_booleanish(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def merge_feature_flag(computed, explicit):
    return computed if explicit is None else explicit


def normalize_paths(raw_paths):
    normalized = {}
    if not isinstance(raw_paths, dict):
        return normalized
    for key, value in raw_paths.items():
        trimmed = str(key).strip()
        normalized[trimmed] = value
        if trimmed.endswith("/"):
            normalized[trimmed[:-1]] = value
        else:
            normalized[f"{trimmed}/"] = value
    return normalized


def compute_capabilities(openapi, spec_source):
    paths = normalize_paths(openapi.get("paths") if isinstance(openapi, dict) else {})

    def has(path: str) -> bool:
        return path in paths

    has_stt = (
        has("/api/v1/audio/transcriptions")
        or has("/api/v1/audio/transcriptions/health")
        or has("/api/v1/audio/stream/transcribe")
        or has(AUDIO_CHAT_STREAM_PATH)
    )
    has_tts = (
        has("/api/v1/audio/speech")
        or has("/api/v1/audio/health")
        or has("/api/v1/audio/voices/catalog")
        or has(AUDIO_CHAT_STREAM_PATH)
    )
    has_voice_chat = has(AUDIO_CHAT_STREAM_PATH) or (has_stt and has_tts)
    has_transport = False if spec_source == "fallback" else has(AUDIO_CHAT_STREAM_PATH)
    return {
        "hasStt": has_stt,
        "hasTts": has_tts,
        "hasVoiceChat": has_voice_chat,
        "hasVoiceConversationTransport": has_transport,
        "openapiHasAudioChatStream": has(AUDIO_CHAT_STREAM_PATH),
    }


def apply_docs_info_gates(computed, docs_info):
    return {
        "hasStt": merge_feature_flag(computed["hasStt"], extract_feature_flag(docs_info, "hasStt")),
        "hasTts": merge_feature_flag(computed["hasTts"], extract_feature_flag(docs_info, "hasTts")),
        "hasVoiceChat": merge_feature_flag(
            computed["hasVoiceChat"],
            extract_feature_flag(docs_info, "hasVoiceChat"),
        ),
        "hasVoiceConversationTransport": merge_feature_flag(
            computed["hasVoiceConversationTransport"],
            extract_feature_flag(docs_info, "hasVoiceConversationTransport"),
        ),
    }


def normalize_health_status(value):
    return str(value or "").strip().lower().replace("_", "-")


def is_ready_tts_status(value):
    normalized = normalize_health_status(value)
    return bool(normalized) and normalized in READY_TTS_STATUSES


def unwrap_health_payload(payload):
    if not isinstance(payload, dict):
        return payload, None
    if isinstance(payload.get("data"), dict):
        status = payload.get("status")
        return payload["data"], int(status) if isinstance(status, int) else None
    status = payload.get("status")
    return payload, int(status) if isinstance(status, int) else None


results = []
required_failures = []


def emit(status, label, detail, required=False):
    results.append((status, label, detail))
    if required and status == "FAIL":
        required_failures.append(label)


docs_status, docs_exit, _, docs_json, docs_valid_json = load_response("docs_info")
openapi_status, openapi_exit, _, openapi_json, openapi_valid_json = load_response("openapi")
stt_status, stt_exit, _, stt_json, stt_valid_json = load_response("stt_health")
tts_status, tts_exit, _, tts_json, tts_valid_json = load_response("tts_health")

spec_source = "authoritative" if openapi_status == 200 and openapi_valid_json and isinstance(openapi_json, dict) else "fallback"
computed_caps = compute_capabilities(openapi_json, spec_source)
effective_caps = apply_docs_info_gates(computed_caps, docs_json)

if docs_status == 200 and docs_valid_json and isinstance(docs_json, dict):
    emit("PASS", "docs-info reachable", "Server returned /api/v1/config/docs-info.")
else:
    emit(
        "WARN",
        "docs-info reachable",
        f"/api/v1/config/docs-info did not return usable JSON (http={docs_status}, curl_exit={docs_exit}).",
    )

if openapi_status == 200 and openapi_valid_json and isinstance(openapi_json, dict):
    emit("PASS", "OpenAPI reachable", "Server returned /openapi.json.")
else:
    emit(
        "WARN",
        "OpenAPI reachable",
        f"/openapi.json did not return usable JSON (http={openapi_status}, curl_exit={openapi_exit}); client would use fallback spec.",
    )

emit(
    "PASS" if computed_caps["openapiHasAudioChatStream"] else "WARN",
    "OpenAPI audio chat route",
    (
        f'{AUDIO_CHAT_STREAM_PATH} is present in /openapi.json.'
        if computed_caps["openapiHasAudioChatStream"]
        else f'{AUDIO_CHAT_STREAM_PATH} is not present in /openapi.json.'
    ),
)

emit(
    "PASS" if effective_caps["hasVoiceConversationTransport"] else "FAIL",
    "Effective voice transport gate",
    (
        "Final merged capabilities report hasVoiceConversationTransport=true."
        if effective_caps["hasVoiceConversationTransport"]
        else "Final merged capabilities report hasVoiceConversationTransport=false."
    ),
    required=True,
)

emit(
    "PASS" if effective_caps["hasVoiceChat"] else "FAIL",
    "Effective voice chat capability",
    (
        "Final merged capabilities report hasVoiceChat=true."
        if effective_caps["hasVoiceChat"]
        else "Final merged capabilities report hasVoiceChat=false."
    ),
    required=True,
)

emit(
    "PASS" if effective_caps["hasStt"] else "FAIL",
    "Effective STT capability",
    (
        "Final merged capabilities report hasStt=true."
        if effective_caps["hasStt"]
        else "Final merged capabilities report hasStt=false."
    ),
    required=True,
)

emit(
    "PASS" if effective_caps["hasTts"] else "FAIL",
    "Effective TTS capability",
    (
        "Final merged capabilities report hasTts=true."
        if effective_caps["hasTts"]
        else "Final merged capabilities report hasTts=false."
    ),
    required=True,
)

if not effective_caps["hasStt"]:
    emit(
        "FAIL",
        "STT health gate",
        "Client would treat STT as unavailable because hasStt=false.",
        required=True,
    )
else:
    stt_payload, stt_wrapped_status = unwrap_health_payload(stt_json)
    if stt_exit != 0 or stt_status == 0 or stt_status >= 400 or not stt_valid_json or not isinstance(stt_payload, dict):
        emit(
            "PASS",
            "STT health gate",
            f"Health probe is not decisively unhealthy (http={stt_status}, curl_exit={stt_exit}); client would fail open to unknown.",
            required=True,
        )
    elif stt_wrapped_status == 404:
        emit(
            "PASS",
            "STT health gate",
            "Health probe reported wrapped 404; client would treat STT health as unknown.",
            required=True,
        )
    else:
        provider = str(stt_payload.get("provider") or "").strip().lower()
        available = bool(stt_payload.get("available", False))
        usable = bool(stt_payload.get("usable", available))
        on_demand = bool(stt_payload.get("on_demand", False))
        fail_open_for_non_whisper = (not available) and bool(provider) and provider != "whisper"
        unhealthy = (not available) and (not usable) and (not on_demand) and (not fail_open_for_non_whisper)
        emit(
            "FAIL" if unhealthy else "PASS",
            "STT health gate",
            (
                f"STT health is blocking (provider={provider or 'unknown'}, available={available}, usable={usable}, on_demand={on_demand})."
                if unhealthy
                else f"STT health is usable (provider={provider or 'unknown'}, available={available}, usable={usable}, on_demand={on_demand})."
            ),
            required=True,
        )

if not effective_caps["hasTts"]:
    emit(
        "FAIL",
        "TTS health gate",
        "Client would treat TTS as unavailable because hasTts=false.",
        required=True,
    )
else:
    tts_payload, tts_wrapped_status = unwrap_health_payload(tts_json)
    if tts_exit != 0 or tts_status == 0 or tts_status >= 400 or not tts_valid_json or not isinstance(tts_payload, dict):
        emit(
            "PASS",
            "TTS health gate",
            f"Health probe is not decisively unhealthy (http={tts_status}, curl_exit={tts_exit}); client would fail open to unknown.",
            required=True,
        )
    elif tts_wrapped_status == 404:
        emit(
            "PASS",
            "TTS health gate",
            "Health probe reported wrapped 404; client would treat TTS health as unknown.",
            required=True,
        )
    else:
        overall_status = normalize_health_status(tts_payload.get("status"))
        overall_ready = True if not overall_status else is_ready_tts_status(overall_status)
        provider_status = None
        if provider_hint:
            provider_details = tts_payload.get("providers", {}).get("details", {})
            if isinstance(provider_details, dict):
                detail = provider_details.get(provider_hint)
                if isinstance(detail, dict):
                    provider_status = detail.get("availability") or detail.get("status")
            if provider_status is None:
                envelopes = tts_payload.get("capabilities_envelope")
                if isinstance(envelopes, list):
                    for entry in envelopes:
                        if not isinstance(entry, dict):
                            continue
                        provider_name = str(entry.get("provider") or "").strip().lower()
                        if provider_name == provider_hint:
                            provider_status = entry.get("availability")
                            break
        selected_provider_ready = overall_ready if provider_status is None else is_ready_tts_status(provider_status)
        unhealthy = not selected_provider_ready
        detail_bits = [f"overall_status={overall_status or 'unknown'}"]
        if provider_hint:
            detail_bits.append(f"provider={provider_hint}")
            detail_bits.append(f"provider_status={normalize_health_status(provider_status) or 'missing'}")
        emit(
            "FAIL" if unhealthy else "PASS",
            "TTS health gate",
            (
                "TTS health is blocking (" + ", ".join(detail_bits) + ")."
                if unhealthy
                else "TTS health is usable (" + ", ".join(detail_bits) + ")."
            ),
            required=True,
        )

print("Voice Conversation Backend Gate Check")
print("====================================")
print(f"Spec source emulation: {spec_source}")
print(f"Selected TTS provider hint: {provider_hint or 'none'}")
print("")
for status, label, detail in results:
    print(f"[{status}] {label}: {detail}")

print("")
if required_failures:
    print("Overall result: FAIL")
    print("Blocking gates:")
    for label in required_failures:
        print(f"- {label}")
else:
    print("Overall result: PASS")
    print("Server-side gates required for Playground speech-to-speech are satisfied.")

print("")
print("Notes:")
print("- This mirrors the client's merged capability logic and fail-open audio health behavior.")
print("- Client-side auth readiness and TTS config completeness are still required separately.")
PY
