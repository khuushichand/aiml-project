# Persona Setup Analytics Summary Card Design

**Date:** 2026-03-14

## Goal

Add a compact setup analytics summary card to `Profiles` so Persona Garden can
show whether a persona's setup funnel is completing and whether the post-setup
handoff is producing real follow-through.

This slice should:

- reuse the existing `/profiles/{persona_id}/setup-analytics` endpoint
- render a compact summary card only when at least one setup run exists
- keep setup analytics clearly separate from live voice analytics and turn
  detection feedback

## Why This Slice Exists

Setup analytics now exists and already records:

- completion rates
- dry-run vs live-session completion counts
- handoff click rate
- handoff target reach rate
- first post-setup action rate

But that data is still invisible inside Persona Garden. The current `Profiles`
tab shows:

- profile metadata
- setup status
- assistant defaults
- live tuning feedback

That means there is still no product-visible way to answer:

- does this persona's setup usually complete?
- where do runs usually drop off?
- does the handoff actually lead to a first real action?

This slice closes that gap without expanding setup state machines or runtime
voice behavior.

## Scope

### In scope

- one compact setup analytics summary card in `Profiles`
- route-owned fetch of existing setup analytics data
- pure presentation component for the summary card
- focused route/component tests

### Out of scope

- backend API changes
- recent-run tables
- charts or dashboard views
- new setup analytics events
- changes to voice analytics or turn-detection feedback

## Review-Driven Constraints

### 1. The card should stay hidden until real setup history exists

This card should not render an empty analytics shell for personas with no setup
runs. The endpoint already exposes `summary.total_runs`, so the display rule can
be:

- hide when `total_runs === 0`
- show once at least one run exists

### 2. The slice should fail closed

`Profiles` already has multiple cards. If setup analytics fails to load, the
best v1 behavior is:

- no extra error banner
- no partial placeholder state
- simply hide the card

This keeps the profile tab stable and avoids adding another top-level failure
surface.

### 3. Step labels need explicit presentation mapping

`most_common_dropoff_step` comes back as setup step ids such as:

- `persona`
- `voice`
- `commands`
- `safety`
- `test`

The card should map these to user-facing labels:

- `Persona choice`
- `Voice defaults`
- `Starter commands`
- `Safety and connections`
- `Test and finish`

If the backend ever returns an unknown step value, the UI should fall back to:

- a title-cased/raw label when possible, or
- `None yet`

### 4. The route should keep setup analytics separate from voice analytics

`sidepanel-persona.tsx` already fetches voice analytics for:

- `commands`
- `test-lab`
- `profiles`

This slice should add separate route state for setup analytics rather than
reusing the existing voice analytics bucket. The two data sets answer different
questions and should not share loading/error state.

### 5. Use a narrow typed response shape on the frontend

The backend schema already exists in Python, but the frontend does not have a
typed setup analytics response. The route should introduce a small explicit
TypeScript type for the summary it consumes rather than passing anonymous JSON
through `ProfilePanel`.

## Chosen Approach

Add a dedicated `PersonaSetupAnalyticsCard` to `Profiles`, backed by a separate
route-owned fetch of the existing setup analytics endpoint.

Concretely:

1. Add route state for `setupAnalytics` and `setupAnalyticsLoading`.
2. Fetch setup analytics only when `Profiles` is active and a persona is
   selected.
3. Pass the typed payload into `ProfilePanel`.
4. Render a compact summary card between `PersonaSetupStatusCard` and
   `AssistantDefaultsPanel`.
5. Hide the card when there are no recorded setup runs.

This is the smallest coherent user-facing follow-up to the completed setup
analytics work.

## Product Shape

The card should answer one narrow question:

> How healthy is setup and post-setup follow-through for this persona?

Suggested sections:

- `Completion rate`
- `Most common drop-off`
- `Dry run completions`
- `Live session completions`
- `Handoff click rate`
- `Target reached rate`
- `First next-step rate`

The card should remain compact and text-first, similar in density to the other
Persona Garden profile cards.

## Data Flow

### Route ownership

In `sidepanel-persona.tsx`:

- add `setupAnalytics` state
- add `setupAnalyticsLoading` state
- fetch `/api/v1/persona/profiles/{persona_id}/setup-analytics?days=30&limit=5`
- only fetch when:
  - `activeTab === "profiles"`
  - `selectedPersonaId` is present

Clear the setup analytics payload when:

- no persona is selected
- the selected persona changes

### Panel composition

In `ProfilePanel.tsx`:

- add optional props for setup analytics payload/loading
- render the new card between:
  - `PersonaSetupStatusCard`
  - `AssistantDefaultsPanel`

This keeps fetching in the route and presentation in the panel/component layer.

## Card Behavior

Create a presentational component:

- `PersonaSetupAnalyticsCard.tsx`

Behavior rules:

- if `loading` and no payload exists: show compact loading copy
- if `summary.total_runs === 0`: render nothing
- if payload exists and `total_runs > 0`: render the summary card
- if fetch fails: render nothing

Formatting rules:

- rates shown as rounded percentages
- count values shown as whole numbers
- `most_common_dropoff_step` mapped to readable labels
- missing drop-off step shown as `None yet`

## Testing Strategy

### Component tests

Add `PersonaSetupAnalyticsCard.test.tsx` covering:

- hidden when `total_runs === 0`
- loading state when `loading === true` and no payload exists
- metric rendering when payload exists
- drop-off label mapping and fallback behavior

### Route tests

Extend `sidepanel-persona.test.tsx` to prove:

- `Profiles` tab fetches setup analytics
- non-`Profiles` tabs do not fetch setup analytics
- setup analytics render the card once returned
- personas with zero runs do not show the card

### Panel/i18n coverage

Update the existing Persona Garden panel i18n coverage if needed so the new
heading is routed through `react-i18next`.

## Success Criteria

This slice is complete when:

1. `Profiles` fetches setup analytics separately from voice analytics.
2. A compact setup analytics card appears only for personas with recorded setup
   history.
3. The card presents readable drop-off and funnel metrics.
4. No backend changes are required.
5. Focused route/component tests pass.
