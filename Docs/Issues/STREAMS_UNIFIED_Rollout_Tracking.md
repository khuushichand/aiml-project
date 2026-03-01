# Tracking Issue — STREAMS_UNIFIED Flip (Dev → Staging → Prod)

Status: Complete
Owner: Streaming/Platform
Created: 2025-11-04

Goal
- Validate unified SSE/WS streams behind `STREAMS_UNIFIED` and flip the flag ON in staging, then plan production.

References
- PRD: `Docs/Product/Completed/Stream_Abstraction_PRD.md` (Status: Pilot Rollout)
- Dev Overlay: `Dockerfiles/docker-compose.dev.yml`
- Metrics Dashboard: `Docs/Monitoring/Grafana_Dashboards/README.md`

Checklist

Phase A — Dev validation
- [x] Start API with dev overlay or `STREAMS_UNIFIED=1` env
- [x] Configure two providers (e.g., OpenAI + Groq)
- [x] Chat SSE (main): single `[DONE]`, OpenAI deltas present
- [x] Character chat SSE: heartbeat under idle; single `[DONE]`
- [x] Chat document-generation SSE: heartbeat; no duplicate `[DONE]`
- [x] Embeddings orchestrator SSE: `event: summary` frames periodic
- [x] Prompt Studio SSE fallback: initial state + heartbeats
- [x] Audio WS: pings observed; quota or validation error emits error frame and closes with correct code
- [x] MCP WS: JSON-RPC responses unchanged; lifecycle frames present; idle close works
- [x] Metrics present: `sse_enqueue_to_yield_ms`, `sse_queue_high_watermark`, `ws_send_latency_ms`, `ws_pings_total`

Phase B — Staging flip
- [x] Enable `STREAMS_UNIFIED=1` in staging
- [x] Use dev overlay in non‑prod: `docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.dev.yml up -d --build`
- [x] Import Grafana dashboard and confirm labels for key endpoints
- [x] Soak for 48h; watch idle timeouts and ping failures
- [x] Document any client compatibility issues (Audio `error_type` alias still on)
- [x] If regressions: toggle back to `STREAMS_UNIFIED=0` (rollback) and file follow-ups

Phase C — Production plan
- [x] Announce window; confirm client compatibility (Audio/MCP consumers)
- [x] Flip `STREAMS_UNIFIED=1` progressively (canary)
- [x] Verify metrics; no duplicate `[DONE]`; latency within ±1% server-side target
- [x] Keep rollback knob in runbook

Notes
- Prefer `STREAM_HEARTBEAT_MODE=data` behind reverse proxies/CDNs.
- For provider control lines (`event/id/retry`), keep `STREAM_PROVIDER_CONTROL_PASSTHRU=0` unless a specific integration requires it.

Follow-ups

- [x] Remove legacy SSE helpers no longer used by pilot endpoints
  - Removed `_extract_sse_data_lines` from `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`.
  - Remaining legacy fallbacks guarded by `STREAMS_UNIFIED` will be removed after the default flip.
- [ ] Confirm Audio `error_type` deprecation timeline with owners (PRD phases target v0.1.1 → v0.1.3)
  - Align release notes and client notices; keep `compat_error_type=True` until v0.1.3.
- [ ] Monitor dashboards after staging flip; record p95 WS send latency and SSE enqueue→yield p95 snapshots pre/post flip.
