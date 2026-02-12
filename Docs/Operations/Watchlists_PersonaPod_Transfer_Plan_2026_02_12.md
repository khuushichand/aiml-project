# Watchlists PersonaPod Transfer Plan (2026-02-12)

## Scope

Address the review findings by improving `tldw_server2` watchlists behavior and tooling using PersonaPod as pattern inspiration only (no direct code port).

## Tracked Issues

1) API/schema mismatch: `generate_audio` family fields are accepted by `WatchlistOutputCreateRequest` but not honored by `POST /api/v1/watchlists/outputs`.

2) Docs/runbook drift: migration runbook and API docs include stale or incomplete watchlists guidance.

3) Tooling discoverability gap: no obvious one-command watchlists audio smoke workflow.

4) Guardrails: document that PersonaPod internals are not a copy source; only high-level operator UX patterns are transferable.

## Coverage Map (All Identified Items)

1) API/schema mismatch  
Covered by: PR1 (completed)

2) Docs/runbook drift  
Covered by: PR3 (completed)

3) Tooling discoverability gap  
Covered by: PR2 (in progress; script + make target complete, CLI wrapper optional)

4) Non-transplant guardrail  
Covered by: Scope + PR3 documentation note

## Delivery Plan

### PR1 - Output API contract alignment (completed)

- [x] Wire `generate_audio`, `target_audio_minutes`, `audio_model`, `audio_voice`, `audio_speed`, `llm_provider`, `llm_model`, `voice_map` into `POST /watchlists/outputs`.
- [x] Trigger watchlists audio briefing workflow from output creation when requested.
- [x] Persist returned workflow task id in run stats (`audio_briefing_task_id`) so `/runs/{run_id}/audio` can resolve status/artifacts.
- [x] Include audio briefing status/task metadata on created output response metadata.
- [x] Add/adjust API tests for payload-driven audio trigger.

### PR2 - Tooling ergonomics

- [x] Add `Helper_Scripts/watchlists/watchlists_audio_smoke.py` to execute create source/job/run/output/audio-check flow.
- [x] Add `Makefile` target(s) for the smoke workflow.
- [ ] Optional: add watchlists CLI command wrapper under `tldw_Server_API/cli/commands`.

### PR3 - Docs and runbook sync

- [x] Update `Docs/Operations/Watchlists_Subscriptions_Migration_Runbook.md` to reflect shipped filter endpoints.
- [x] Replace future-state script placeholders with current helper scripts/commands.
- [x] Expand `Docs/API-related/Watchlists_API.md` outputs section with TTS and audio briefing examples.
- [x] Add a short note explicitly prohibiting direct PersonaPod code transplant and listing anti-patterns observed in review.

## Acceptance Criteria

- `POST /watchlists/outputs` with `generate_audio=true` enqueues workflow and exposes task id in metadata.
- `/watchlists/runs/{run_id}/audio` returns pending/completed against the task id set by outputs API flow.
- Existing watchlists output tests continue passing; new coverage added for payload-driven audio behavior.
- Docs examples match current endpoint behavior and field names.
