# Persona Turn Detection Feedback Design

## Goal

Add persona-scoped tuning feedback for live voice so users can review recent
live-session behavior, see the exact turn-detection settings those sessions
used, and make better saved-defaults decisions from `Profiles -> Assistant
Defaults`.

This slice should help answer one product question well:

- “Are my current turn-detection defaults working, and if not, what should I
  try next?”

## Scope

This slice is limited to:

- persona live-voice session-summary persistence
- persona analytics API expansion for recent live-session summaries
- a route/client flush path for client-owned recovery counts
- a Profiles-side tuning feedback card next to saved turn-detection defaults
- light recommendation copy based on documented heuristics

This slice does not add:

- full turn-level live-voice history
- cross-persona comparisons
- a dedicated Analytics tab
- opaque scoring or model-driven tuning suggestions
- automatic default changes

## Review-Driven Constraints

### Current Backend Analytics Are Aggregate-Only

The live-voice response currently exposes only aggregate counts:

- `total_committed_turns`
- `vad_auto_commit_count`
- `manual_commit_count`
- `vad_auto_rate`
- `manual_commit_rate`
- `degraded_session_count`

There is no per-session summary model and no stored record of the
turn-detection settings used by each live session.

This means the design must explicitly add session-summary persistence instead of
pretending the existing API can be reshaped into a recent-sessions view.

### Recovery Signals Are Client-Owned Today

`listening_stuck` and `thinking_stuck` are produced by the Persona Garden live
voice controller, not by the backend websocket runtime.

If tuning feedback wants to use recovery counts, it needs an explicit
client-to-server flush or patch path. Those numbers do not already exist in the
backend analytics store.

### Profiles Does Not Currently Load Voice Analytics

`sidepanel-persona.tsx` only loads voice analytics when `Commands` or `Test Lab`
is active. A new tuning card in `Profiles` would stay empty unless that route
loading rule changes.

### Mid-Session Tuning Changes Need Clear Attribution

Live turn-detection settings can change immediately during a connected session.
If one session can span multiple settings configurations, a tuning-feedback
model must choose how to attribute that session:

- snapshot settings only once at session start, or
- segment analytics when settings change

V1 should choose one simple, explicit rule.

### Avoid Duplicating Existing Aggregate Analytics

Persona Garden already has a live-usage summary in the command analytics area.
The new feedback card should not become a second copy of the same aggregate
numbers without a more specific purpose.

Its role should be tuning guidance, not generic usage reporting.

## Chosen Approach

Add persona-scoped `live_voice_session_summaries` on the backend, keyed by
`session_id`, and store a session-start snapshot of the turn-detection settings
used for that session.

The backend remains the source of truth for persisted summaries and aggregate
counts. The client contributes only the recovery metrics it currently owns.

The UI will surface this first in `Profiles -> Assistant Defaults` as a
`Recent live tuning feedback` card that combines:

- current 7-day tuning-oriented summary metrics
- a short recent-session list
- light, conservative suggestions when the data is strong enough

## Data Model

### New Session Summary Record

Add a new persona-scoped live-voice session summary record with one row per
`session_id`.

Recommended fields:

- `user_id`
- `persona_id`
- `session_id`
- `created_at`
- `updated_at`
- `started_at`
- `ended_at`
- `auto_commit_enabled`
- `vad_threshold`
- `min_silence_ms`
- `turn_stop_secs`
- `min_utterance_secs`
- `turn_detection_changed_during_session`
- `total_committed_turns`
- `vad_auto_commit_count`
- `manual_commit_count`
- `manual_mode_required_count`
- `text_only_tts_count`
- `listening_recovery_count`
- `thinking_recovery_count`

The exact turn-detection values are stored as numbers and booleans, not as a
preset label. Preset labels remain derived on the frontend.

### Session-Start Snapshot Rule

V1 should snapshot turn-detection settings from the first usable `voice_config`
for a session and keep that snapshot stable for the life of that session.

If the user changes turn-detection values after the snapshot:

- do not rewrite the stored session settings
- set `turn_detection_changed_during_session = true`

That keeps storage simple and gives the UI a trustworthy rule:

- show mixed sessions in the recent list
- exclude mixed sessions from recommendation heuristics

### Backend Event Ownership

The backend owns:

- `vad_auto_commit_count`
- `manual_commit_count`
- `manual_mode_required_count`
- `text_only_tts_count`
- `started_at`
- `ended_at`

The client owns:

- `listening_recovery_count`
- `thinking_recovery_count`

Those client-owned counts should be flushed into the backend session summary
with an explicit API call.

## Backend Contract

### Session Summary Lifecycle

Create or update the session summary from the persona websocket runtime:

1. On the first `voice_config` for a live session:
   - create the summary row if missing
   - store the initial turn-detection settings snapshot
   - set `started_at`
2. On later `voice_config` messages:
   - compare against the stored snapshot
   - if values differ, set `turn_detection_changed_during_session = true`
3. On voice commit events:
   - increment `total_committed_turns`
   - increment either `vad_auto_commit_count` or `manual_commit_count`
4. On degraded-mode notices:
   - increment `manual_mode_required_count`
   - increment `text_only_tts_count` when text-only TTS degradation is active
5. On websocket close / disconnect:
   - set `ended_at`

### Client Flush Endpoint

Add an explicit upsert/finalize endpoint for client-owned recovery counts.

Recommended shape:

- `PUT /api/v1/persona/profiles/{persona_id}/voice-analytics/live-sessions/{session_id}`

Body:

- `listening_recovery_count`
- `thinking_recovery_count`
- optional `ended_at` or `finalize: true`

Semantics:

- idempotent upsert for the client-owned counters
- best-effort finalization on disconnect/unmount/reconnect
- safe to call multiple times for the same session

### Analytics Response Expansion

Extend the persona voice analytics response with:

- existing aggregate `live_voice`
- new `recent_live_sessions`

Each recent session item should include:

- `session_id`
- `started_at`
- `ended_at`
- exact turn-detection values
- `turn_detection_changed_during_session`
- committed-turn counts
- recovery counts
- degraded counts

Keep the existing aggregate response intact so current Commands/Test Lab usage
summary code does not break.

## Frontend Model

### Route Loading

Expand the existing persona analytics fetch so it also loads when `Profiles` is
active, not only `Commands` and `Test Lab`.

That keeps one route-owned analytics source for:

- existing command analytics UI
- new Assistant Defaults tuning feedback

### Live Session Flush Behavior

The route should collect client-owned recovery counts from
`usePersonaLiveVoiceController` and flush them to the new backend endpoint:

- when the live session disconnects normally
- before a recovery-driven reconnect
- on route unmount as best effort

V1 can treat this as best-effort. It does not need a perfect crash-proof flush
pipeline.

### Profiles-Side Feedback Card

Add a new card under the saved `Turn detection defaults` block in
`AssistantDefaultsPanel.tsx`.

The card should contain:

1. `Current signal`
   - auto-commit rate
   - manual-send rate
   - recovery rate
2. `Suggested adjustment`
   - shown only when confidence is high enough
3. `Recent sessions`
   - last 5-10 sessions
   - derived preset label
   - exact settings used
   - counts for manual sends, auto-commits, and recovery
   - mark mixed sessions when `turn_detection_changed_during_session` is true

## Suggestion Heuristics

V1 suggestions should be documented, conservative, and easy to explain.

### Minimum Data Requirement

Do not generate a tuning suggestion unless all of these are true:

- at least `3` recent sessions
- at least `8` committed turns across eligible sessions
- at least `2` eligible sessions without
  `turn_detection_changed_during_session`

If the threshold is not met, show metrics only and:

- `No tuning suggestion yet. Run a few live sessions to unlock guidance.`

### Suggest `Fast`

Suggest trying `Fast` when all of these are true:

- manual-send rate across eligible sessions is high
- listening recovery is low
- manual-mode-required count is `0`

Recommended copy:

- `Suggestion: try Fast for quicker commits. Recent sessions needed manual sends often, but auto-commit availability looks healthy.`

### Suggest Checking Auto-Commit Availability First

Do not suggest threshold changes when degraded execution is the bigger problem.

If `manual_mode_required_count > 0`, prefer:

- `Suggestion: check server auto-commit availability before changing thresholds. Recent sessions fell back to manual send because server auto-commit was unavailable.`

### Thinking-Recovery Guidance

If thinking recovery is high, do not blame VAD.

Recommended copy:

- `Suggestion: current turn detection may be fine. Most delays happened after commit, which points to assistant/runtime latency rather than speech cutoff timing.`

### Healthy Neutral State

If auto-commit rate is healthy, manual sends stay low, and recovery counts stay
low:

- `Suggestion: current settings look healthy.`

### Explicit Non-Goals

Do not claim:

- `too many false commits`
- `speech threshold is definitely too low`
- `this preset is wrong`

The available telemetry does not support those conclusions credibly in V1.

## UI Responsibilities

### Commands/Test Lab

Keep the existing command-oriented analytics summary where it is.

It remains responsible for:

- command usage
- fallback rates
- aggregate live-voice usage snapshot

### Profiles -> Assistant Defaults

The new feedback card is responsible for:

- tuning feedback
- recent session context
- recommendation copy

That separation prevents duplicate metric storytelling across tabs.

## Testing Strategy

### Backend

Add coverage for:

- session summary creation from `voice_config`
- commit counters updating per session
- degraded counters updating per session
- recovery-count flush upserts
- `recent_live_sessions` in analytics API output
- `turn_detection_changed_during_session` behavior when live VAD settings change

### Frontend

Add coverage for:

- analytics fetch in `Profiles`
- best-effort recovery-count flush on disconnect/reconnect
- Assistant Defaults feedback card rendering with:
  - sparse data
  - healthy data
  - `try Fast` suggestion
  - `check auto-commit availability` suggestion
- mixed-session exclusion from recommendation logic

## Success Criteria

This slice is complete when:

- persona analytics persist recent live-session summaries with settings snapshots
- Profiles can render recent tuning feedback without opening Commands/Test Lab
- live recovery counts reach the backend through an explicit flush path
- recommendation copy stays conservative and data-backed
- existing command analytics behavior remains intact
