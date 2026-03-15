# /chat Typing Latency Investigation Design

Date: 2026-03-03  
Status: Approved

## Problem Statement

Typing in `/chat` is reported as extremely slow across both:

- WebUI `/chat`
- Extension `/chat`

The slowdown occurs even in a new empty chat, which indicates per-keystroke render/work overhead instead of history-size growth.

## Scope

In scope:

- Shared `/chat` composer paths used by both WebUI and extension
- Root-cause investigation and targeted mitigations
- Validation strategy and rollout safety

Out of scope:

- Full chat architecture rewrite
- Feature removals
- Unrelated route performance work

## Approaches Considered

1. Profiler-first investigation (recommended)
2. Direct mitigation-first (faster, less certain)
3. Architectural isolation-first (largest change)

Recommended approach:

- Use profiler-first to identify true hotspots.
- Apply targeted low-risk mitigations to top offenders only.

## Investigation Design

Primary targets:

- `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Shared hooks/utilities used by composer updates:
  - `useComposerTokens`
  - `useDynamicTextareaSize`
  - `useDraftPersistence`
  - mention/slash command pathways

Measurements to collect:

- Input `onChange` start/end timing
- React render/commit duration for composer subtree
- Cost/frequency of `form.values.message`-dependent derivations

Execution surfaces:

- WebUI `/chat`
- Extension `/chat`

Investigation output:

- Ranked hotspot table with timing and call frequency
- Surface parity notes (WebUI vs extension)
- Regression hypothesis tied to concrete source locations

## Mitigation Design

Goal: preserve behavior while reducing keystroke-to-paint latency.

Plan:

- Keep immediate input path synchronous:
  - textarea value and caret behavior
  - IME handling
  - Enter-to-send behavior
- Separate state concerns:
  - `liveInput` for immediate keystrokes
  - `deferredInput` for non-critical heavy derivations (via deferred value or short debounce)
- Move expensive non-critical work to deferred path:
  - token, insight, and recommendation derivations
  - prompt-analysis helpers not required for immediate typing feedback
- Add recomputation guards to avoid rerunning derived logic when semantic inputs are unchanged
- Reduce autosize layout thrash:
  - batch with `requestAnimationFrame`
  - avoid unnecessary style reset/reflow work per key when height class is effectively unchanged

## Validation and Safety

Validation sequence:

1. Baseline profile (both surfaces, same typing scenario)
2. Apply one mitigation at a time
3. Re-profile with same scenario
4. Compare:
   - input handler timing
   - React commit timing
   - dropped-frame indicators

Correctness guardrails:

- Send payload must always reflect latest typed input
- Slash command, mention insertion, and IME behavior parity checks required
- No change to submission semantics without explicit regression tests

Rollout safety:

- Land as small isolated commits (instrumentation, then each mitigation)
- Keep changes scoped to shared composer modules for easy revert

## Success Criteria

- Noticeable typing responsiveness improvement in both WebUI and extension `/chat`
- Lower measured per-keystroke cost in profiler data
- No regressions in submit behavior, mentions/slash commands, or IME composition
