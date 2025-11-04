# Tracking Issue — STREAMS_UNIFIED Flip (Dev → Staging → Prod)

Status: Open
Owner: Streaming/Platform
Created: 2025-11-04

Goal
- Validate unified SSE/WS streams behind `STREAMS_UNIFIED` and flip the flag ON in staging, then plan production.

References
- PRD: `Docs/Design/Stream_Abstraction_PRD.md` (Status: Pilot Rollout)
- Dev Overlay: `Dockerfiles/Dockerfiles/docker-compose.dev.yml`
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

