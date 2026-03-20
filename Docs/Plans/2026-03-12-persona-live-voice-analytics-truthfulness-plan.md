# Persona Live Voice Analytics Truthfulness Plan

## Stage 1: Lock The Desired Analytics Contract
**Goal**: Define failing backend and frontend tests for persona websocket live-voice telemetry without changing current command analytics semantics.
**Success Criteria**:
- Backend tests prove live voice websocket turns record telemetry for `vad_auto`, `manual`, and degraded manual-mode sessions.
- API tests prove `/persona/profiles/{persona_id}/voice-analytics` returns a new `live_voice` section alongside existing command analytics.
- Frontend tests prove the analytics summary renders the new live-voice metrics without breaking the current command/fallback cards.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q -k 'live_voice'`
- `bunx vitest run src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
**Status**: Complete

## Stage 2: Record Live Voice Telemetry Server-Side
**Goal**: Add server-owned persistence for persona live voice commit source and degraded-manual mode, then expose aggregate analytics from the persona API.
**Success Criteria**:
- Persona websocket records one live-voice event per committed spoken turn with `commit_source`.
- Persona websocket records degraded/manual-mode session occurrences without double-counting on every chunk.
- Persona analytics response includes truthful live-voice summary metrics while preserving existing command/fallback analytics.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q`
**Status**: Complete

## Stage 3: Surface Live Voice Metrics In Persona Garden
**Goal**: Extend the existing analytics summary card to show live voice auto/manual/degraded metrics in a way that complements, not replaces, command analytics.
**Success Criteria**:
- `CommandAnalyticsSummary` renders the new live-voice metrics.
- `sidepanel-persona` continues to fetch and pass one analytics payload shape.
- Existing Commands/Test Lab analytics behavior remains intact.
**Tests**:
- `bunx vitest run src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
**Status**: Complete

## Stage 4: Verification And Commit
**Goal**: Run full verification for touched backend/frontend scope and commit the slice.
**Success Criteria**:
- Targeted backend and frontend suites pass.
- `py_compile`, Bandit, and `git diff --check` pass on touched scope.
- Worktree is clean after commit.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q`
- `bunx vitest run src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
- `python -m py_compile tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/core/VoiceAssistant/db_helpers.py`
- `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/core/VoiceAssistant/db_helpers.py -f json -o /tmp/bandit_persona_live_voice_analytics.json`
- `git diff --check`
**Status**: Complete
