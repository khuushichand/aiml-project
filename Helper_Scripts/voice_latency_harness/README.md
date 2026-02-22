# Voice Latency Harness

Purpose: quick, reproducible latency snapshots for:
- `stt_final_latency_seconds`
- `tts_ttfb_seconds`
- `voice_to_voice_seconds`
- `audio_chat_latency_seconds` (when available)

Primary script: `Helper_Scripts/voice_latency_harness/run.py`

## Requirements
- Python 3.11+
- Running API server (`python -m uvicorn tldw_Server_API.app.main:app --reload`)
- Optional dependencies:
  - `soundfile` for full mode synthetic WAV generation
  - `prometheus_client` when `/metrics` is exposed in Prometheus text format

## Usage
- Short mode (CI-friendly, metrics scrape only):
  - `python Helper_Scripts/voice_latency_harness/run.py --out out.json --short`
- Full mode (executes a real `/api/v1/audio/chat` turn):
  - `python Helper_Scripts/voice_latency_harness/run.py --out out.json --base-url http://127.0.0.1:8000 --api-key YOUR_KEY`
- Multiple iterations:
  - `python Helper_Scripts/voice_latency_harness/run.py --out out.json --short --runs 3`

## Output Schema
The harness writes JSON with this top-level shape:

```json
{
  "run_id": "voice-latency-...",
  "fixture": {
    "mode": "short|full",
    "base_url": "http://127.0.0.1:8000",
    "source": "metrics_scrape|/api/v1/audio/chat"
  },
  "runs": {
    "requested": 1,
    "completed": 1,
    "mode": "short|full",
    "started_at": "2026-02-07T00:00:00Z",
    "finished_at": "2026-02-07T00:00:01Z",
    "duration_seconds": 1.0
  },
  "metrics": {
    "stt_final_latency_seconds": {"p50": 0.0, "p90": 0.0},
    "tts_ttfb_seconds": {"p50": 0.0, "p90": 0.0},
    "voice_to_voice_seconds": {"p50": 0.0, "p90": 0.0}
  },
  "raw_metrics": {}
}
```

## Interpreting Results
- Use `p50` to track typical latency.
- Use `p90` to track tail behavior/regressions.
- Empty maps (for example `{}` under a metric) mean the series was not present in the metrics scrape window.
- In full mode, if `audio_chat_latency_seconds` histogram is missing, measured request latency is used as fallback.

## Troubleshooting
- Server unavailable / timeout:
  - Verify server is running and reachable at `--base-url`.
  - Check `curl http://127.0.0.1:8000/metrics`.
- Auth errors:
  - Provide `--api-key` and confirm it matches server auth mode.
  - In single-user mode, verify `SINGLE_USER_API_KEY`.
- Empty metric percentiles:
  - Generate traffic first (run `/audio/chat` or WS routes), then rerun short mode.
  - Confirm relevant metric names exist in `/metrics`.
- Missing dependencies:
  - `soundfile` missing: install it for full mode.
  - `prometheus_client` missing: install it if `/metrics` is not JSON.

## Related
- Protocol docs: `Docs/Audio_Streaming_Protocol.md`
- STT overview: `Docs/Audio_STT_Module.md`
- Examples: `Helper_Scripts/voice_latency_harness/examples/`
