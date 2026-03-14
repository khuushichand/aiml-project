# Presentation Studio Render Timing And Transitions Design

## Overview

This design makes the Presentation Studio timing and transition controls real in exported video. The current UI supports slide-level transition presets and manual timing, but the backend renderer still treats every slide as a still-image segment and concatenates them with hard cuts.

The revised render pipeline keeps the existing slide-frame generation and asset materialization model, but changes how durations and final assembly are resolved:

- manual timing can extend a narrated slide without trimming narration
- non-cut transitions render after each slide's effective duration without overlapping narration
- all-cut decks stay on the cheap concat path
- decks with real transitions switch to a filtered final video assembly path

## Constraints From Current Backend

The current renderer has four constraints that shape the implementation:

1. Audio-backed segments currently stop at narration end.
   - `_build_segment_command()` uses `-shortest` whenever an audio track exists.
   - Manual timing padding therefore requires explicit audio padding plus `-t <effective_duration>`.

2. Final assembly is currently concat-copy only.
   - `_build_concat_command()` uses the concat demuxer with `-c copy`.
   - Any `xfade` transition requires a filtered final encode instead of concat-copy.

3. Runtime is currently a plain sum of slide durations.
   - That is insufficient once visual overlap enters the pipeline.

4. Audio duration is metadata-first.
   - `_estimate_slide_duration_seconds()` trusts `audio.duration_ms` and then falls back straight to a notes heuristic.
   - If an audio asset exists but metadata duration is absent or stale, the renderer should probe the actual asset duration before using the heuristic.

## Timing Semantics

Effective slide duration resolves in this order:

1. If a slide has a narration asset and a valid `audio.duration_ms`, use that audio duration.
2. If a slide has a narration asset but metadata duration is missing, probe the materialized asset duration with `ffprobe`.
3. If `timing_mode` is `manual`, final effective duration is `max(audio_duration, manual_duration)`.
4. If there is no usable narration duration, fall back to the existing speaker-notes word-count estimate.

Manual timing never trims narration. It only extends a slide with additional hold time.

## Transition Semantics

Supported UI presets map to backend transitions as follows:

- `cut` -> hard cut
- `fade` -> `xfade=fade`
- `wipe` -> `xfade=wipeleft`
- `zoom` -> `xfade=zoomin`

Transition duration is a single backend constant for v1, likely `0.75s`.

Transitions are visual-only in v1. Audio remains sequential and non-overlapping.

Each non-cut transition begins after the outgoing slide's effective duration. To make that work with `xfade` without shortening the deck runtime, the renderer extends the outgoing visual clip by one transition-duration hold buffer. The overlap then happens inside that extra visual-only buffer instead of inside the authored slide duration.

This yields three useful properties:

- narration never overlaps with incoming-slide visuals
- manual timing remains the real hold duration before the next slide starts appearing
- final deck runtime still matches the sum of authored slide durations

## Render Pipeline

The renderer splits into two execution paths.

### Path A: All Boundaries Resolve To `cut`

Keep the current segment-first architecture:

- render one frame per slide
- materialize one audio asset per slide if present
- build one media segment per slide
- concatenate segments into the final output

The key change is narrated segment generation:

- when audio is present, use padded audio plus explicit `-t <effective_duration>`
- use `apad` so manual timing can extend the segment past narration end
- avoid relying on `-shortest` for narrated slides

This path preserves the current cheap concat behavior for the common case of hard cuts.

### Path B: At Least One Boundary Resolves To A Real Transition

Replace concat-copy final assembly with a filtered final encode.

The pipeline becomes:

1. Render one still-video source per slide at its effective duration.
2. Build the video timeline with chained `xfade` transitions.
3. Build the audio timeline separately from padded sequential slide audio clips.
4. Mux final video and audio into the requested format.

To preserve overall runtime while using `xfade`, each slide that transitions out visually gets an extra video-only hold buffer equal to the transition duration. The xfade offset is placed at the outgoing slide's effective end, so the overlap occurs inside that added hold buffer and the final deck runtime still matches the sum of effective slide durations.

Audio stays sequential:

- narration plays once, from the start of its slide
- manual timing longer than narration pads with silence
- no `acrossfade`

This makes the export match the authored timing model without creating overlapping speech.

## Runtime And Timeout Semantics

Timeout budgeting must use resolved final runtime, not a naive sum from the old segment model.

For all-cut decks:

- final runtime is the sum of effective slide durations

For transitioned decks:

- final runtime is still the sum of effective slide durations
- outgoing slides receive extra visual hold to absorb the xfade overlap
- timeout should be based on that final runtime, not on intermediate buffered clip lengths alone

## Failure Behavior

- invalid or missing transition metadata falls back to `fade`
- invalid manual duration falls back to auto timing
- missing `audio.duration_ms` on a slide with narration triggers asset-duration probing
- if duration probing fails, the renderer falls back to the existing notes heuristic
- if filtered transition assembly fails, the render fails explicitly rather than silently producing the wrong output

## Testing Strategy

The implementation should stay TDD-first and extend the existing Slides render tests.

Required coverage:

- duration resolution with metadata and `ffprobe` fallback
- manual timing padding for narrated slides
- transition mapping from UI preset to ffmpeg filter name
- transitioned deck runtime preserving the sum of effective slide durations
- transition mapping from UI preset to ffmpeg filter name
- cut-only decks still using the concat path
- transitioned decks using filtered final video assembly
- timeout/runtime math using resolved deck runtime

The first implementation pass should stay command-generation focused. It is enough to prove that the renderer chooses the correct path, computes the correct durations, and emits the correct ffmpeg arguments without requiring a full end-to-end video-content assertion.
