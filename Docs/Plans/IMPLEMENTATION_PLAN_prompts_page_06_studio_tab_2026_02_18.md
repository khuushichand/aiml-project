# Implementation Plan: Prompts Page - Studio Tab

## Scope

Components: `Studio/StudioTabContainer.tsx`, `Studio/QueueHealthWidget.tsx`, `Studio/Prompts/ExecutePlayground.tsx`, related status/provider services
Finding IDs: `6.1` through `6.6`

## Finding Coverage

- Disabled-state explanation and mobile clarity: `6.1`, `6.3`
- Queue status interpretation and freshness: `6.2`, `6.4`
- Execute Playground provider/model UX: `6.5`, `6.6`

## Stage 1: Navigation Clarity and Mobile Usability
**Goal**: Make Studio sub-navigation self-explanatory across desktop and mobile.
**Success Criteria**:
- Disabled sub-tabs expose reason (`Select a project first`) via tooltip/label.
- Mobile presentation avoids icon-only ambiguity (labels, dropdown, or equivalent).
- Disabled-tab interactions route users toward Project selection path.
**Tests**:
- Component tests for disabled-state explanatory content.
- Responsive tests for mobile tab selector readability and actionability.
**Status**: Complete

## Stage 2: Queue Health Interpretation and Polling Strategy
**Goal**: Convert raw status numbers into actionable system feedback.
**Success Criteria**:
- Queue health tooltip/header adds natural-language summary (`Healthy`, `Degraded`).
- Poll interval becomes adaptive (fast when processing, slower when idle).
- Active-job views show fresher progress without excessive request volume.
**Tests**:
- Unit tests for health-summary classification logic.
- Integration tests for adaptive polling interval transitions.
**Status**: Complete

## Stage 3: Execute Playground Provider/Model Selection
**Goal**: Prevent invalid execution configs and improve default visibility.
**Success Criteria**:
- Provider input replaced by validated select populated from configured providers.
- Model input replaced by model select/autocomplete scoped to provider.
- UI shows effective default provider/model when fields are not explicitly set.
- Validation and fallback behavior stay aligned with backend execution endpoint.
**Tests**:
- Integration tests for provider/model loading and dependent selection behavior.
- Form validation tests for unavailable provider/model selections.
- Snapshot test for default placeholder rendering.
**Status**: Complete

## Stage 4: Real-Time Status Path (Longer-Term)
**Goal**: Define and integrate WebSocket-based progress updates for long jobs.
**Success Criteria**:
- WebSocket event contract documented for Studio status updates.
- Frontend subscribes/unsubscribes safely and updates UI incrementally.
- Polling remains as fallback when socket connection unavailable.
**Tests**:
- Integration tests for socket event handling and reconnect behavior.
- Fallback tests validating poll-based updates when sockets fail.
**Status**: Not Started

## Dependencies

- Mobile labeling work should align with accessibility category requirements.
- Provider/model source depends on `GET /api/v1/llm/providers` and related defaults endpoint.
