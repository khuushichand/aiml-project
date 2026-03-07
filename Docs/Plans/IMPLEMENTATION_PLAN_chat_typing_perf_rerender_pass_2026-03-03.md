## Stage 1: Confirm Remaining Hotspots
**Goal**: Verify components still rerendering on composer keystrokes after previous optimizations.
**Success Criteria**: Identify concrete components/props to stabilize for both sidepanel and web `/chat`.
**Tests**: Existing perf probes and static code inspection.
**Status**: Complete

## Stage 2: Reduce Keystroke Rerender Fanout
**Goal**: Prevent expensive non-text controls from rerendering on each input change.
**Success Criteria**: Memoize heavy controls and stabilize callback/prop identities in sidepanel and web composer paths.
**Tests**: TypeScript compile via targeted vitest suites touching composer components.
**Status**: Complete

## Stage 3: Validate Behavior and Perf
**Goal**: Ensure no regressions and measure typing latency deltas.
**Success Criteria**: Relevant tests pass; perf probe shows equal or improved per-char timing and/or fewer long tasks.
**Tests**: `bunx vitest run ...` + out-of-sandbox perf script(s).
**Status**: Complete
