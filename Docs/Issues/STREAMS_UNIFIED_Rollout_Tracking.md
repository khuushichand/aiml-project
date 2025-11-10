# Tracking Issue — STREAMS_UNIFIED Flip (Dev → Staging → Prod)

Status: Open
Owner: Streaming/Platform
Created: 2025-11-04

Goal
- Validate unified SSE/WS streams behind `STREAMS_UNIFIED` and flip the flag ON in staging, then plan production.

References
- PRD: `Docs/Design/Stream_Abstraction_PRD.md` (Status: Pilot Rollout)
- Dev Overlay: `Dockerfiles/docker-compose.dev.yml`
- Metrics Dashboard: `Docs/Deployment/Monitoring/Grafana_Streaming_Basics.json`

Checklist

Phase A — Dev validation
- [ ] Start API with dev overlay or `STREAMS_UNIFIED=1` env
- [ ] Configure two providers (e.g., OpenAI + Groq)
- [ ] Chat SSE (main): single `[DONE]`, OpenAI deltas present
- [ ] Character chat SSE: heartbeat under idle; single `[DONE]`
- [ ] Chat document-generation SSE: heartbeat; no duplicate `[DONE]`
- [ ] Embeddings orchestrator SSE: `event: summary` frames periodic
- [ ] Prompt Studio SSE fallback: initial state + heartbeats
- [ ] Audio WS: pings observed; quota or validation error emits error frame and closes with correct code
- [ ] MCP WS: JSON-RPC responses unchanged; lifecycle frames present; idle close works
- [ ] Metrics present: `sse_enqueue_to_yield_ms`, `sse_queue_high_watermark`, `ws_send_latency_ms`, `ws_pings_total`

Phase B — Staging flip
- [ ] Enable `STREAMS_UNIFIED=1` in staging
- [ ] Use dev overlay in non‑prod: `docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.dev.yml up -d --build`
- [ ] Import Grafana dashboard and confirm labels for key endpoints
- [ ] Soak for 48h; watch idle timeouts and ping failures
- [ ] Document any client compatibility issues (Audio `error_type` alias still on)
- [ ] If regressions: toggle back to `STREAMS_UNIFIED=0` (rollback) and file follow-ups

Phase C — Production plan
- [ ] Announce window; confirm client compatibility (Audio/MCP consumers)
- [ ] Flip `STREAMS_UNIFIED=1` progressively (canary)
- [ ] Verify metrics; no duplicate `[DONE]`; latency within ±1% server-side target
- [ ] Keep rollback knob in runbook

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
