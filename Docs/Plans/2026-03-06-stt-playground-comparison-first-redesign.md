# STT Playground: Comparison-First Redesign

**Date:** 2026-03-06
**Status:** Approved
**Primary workflow:** Record once, transcribe with multiple models, compare results

## Problem Statement

The current SttPlaygroundPage has 12 usability issues identified via Nielsen's 10 heuristics. The most critical: audio blobs are discarded after transcription, making the primary workflow (model comparison) impossible. Users must re-record for every model they want to test.

Secondary issues include no recording feedback (timer, audio level), read-only transcripts, settings on a separate page, no keyboard shortcuts, no copy-to-clipboard, and no confirmation on destructive actions.

## Design Principles

- **Record once, transcribe many** — decouple recording from transcription
- **Comparison is the core interaction** — not an afterthought
- **Progressive disclosure** — casual users see record + results; power users expand settings
- **Playground means experimentation** — inline settings, not navigate-away-to-configure

## Page Layout: Three Zones

### Zone 1 — Recording Strip (top, always visible)

A compact horizontal bar containing:

- **Record/Stop toggle** — large, prominent. Red pulsing dot when recording.
- **Audio level meter** — real-time CSS-animated bars during recording. Uses `role="meter"` with `aria-valuenow`.
- **Duration timer** — counts up during recording, shows final duration after stop.
- **Playback controls** — appear after stop. Lets users re-listen before transcribing.
- **Upload file button** — secondary action for pre-recorded audio files.
- **Gear icon** — toggles inline settings panel (collapsed by default).
- **Keyboard shortcut** — `Space` toggles record/stop when no text input is focused. Shown as hint text.

The audio blob is retained in memory. This is the foundational change enabling comparison.

#### Inline Settings Panel (collapsed by default, toggled by gear icon)

Expands below the recording strip:

- Language, Task, Format, Temperature, Prompt — all editable in-place
- Segmentation toggle with nested params (K, min size, lambda, etc.) — only visible when enabled
- "Reset to defaults" link restores global Settings values
- Changes apply to next transcription only (playground-local state)

### Zone 2 — Comparison Panel (middle, core interaction)

#### Model Selection Bar

- **Multi-select tag input** — pick 1-N models from server list. Each appears as a removable tag.
- **"Transcribe All" button** — sends blob to server once per model, in parallel. Disabled until blob exists.
- **Inline config summary** — language, task, format as compact text. Clicking opens popover to edit in-place.

#### Results Grid

Responsive card grid (1 col mobile, 2 col medium, 3 col large). Each card:

- **Header:** model name
- **Body:** editable textarea with transcript text
- **Metrics row:** transcription latency, word count
- **Actions:** Copy to clipboard, Edit toggle, Save to Notes

Behavioral details:
- Cards show skeleton/spinner independently while in-flight
- Failed cards show inline error with per-card retry
- Cards arrive as results stream in (no waiting for all)
- Adding a model after initial run shows card with individual "Transcribe" button
- Re-recording clears results with "Re-transcribe?" prompt if results exist

### Zone 3 — History Panel (bottom)

Stores past recordings with their comparison results.

Each entry shows:
- Timestamp, duration, number of models compared
- Collapsed preview of each model's first line of transcript
- Actions: Expand, Re-compare (loads blob back to Zone 1+2), Export (to Notes or markdown clipboard), Delete

Storage strategy:
- **IndexedDB** for audio blobs (too large for localStorage)
- **Plasmo storage** for metadata and transcript text
- **Cap:** 20 recordings. Prompt to delete old entries when exceeded.
- **Cleanup:** `URL.revokeObjectURL()` on unmount, IndexedDB entries on delete

Delete behavior:
- Single item: immediate delete + 5-second "Undo" toast (Gmail pattern)
- Clear all: confirmation dialog ("Delete N recordings? Cannot be undone.")

## Keyboard Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Space` | Toggle record/stop | No text input focused |
| `Ctrl/Cmd + Enter` | Transcribe All | Models selected + blob exists |
| `Ctrl/Cmd + Shift + C` | Copy focused result | Result card has focus |

Shortcuts shown as inline hints near corresponding buttons.

## Accessibility

- Record button: dynamic `aria-label` ("Start recording" / "Stop recording" / "Transcribing, please wait")
- Audio level meter: `role="meter"` with `aria-valuenow`
- Result cards: `role="region"` with `aria-label="Transcription result from {model}"`
- Focus management: after "Transcribe All" completes, focus moves to first result card
- Live region: `aria-live="polite"` on transcript areas
- Recording state: red + icon change + text change (not color alone)

## Heuristic Issues Addressed

| # | Heuristic | Fix |
|---|-----------|-----|
| 1 | Visibility of system status | Recording timer + audio level meter |
| 2 | Visibility of system status | Skeleton loaders per card, streaming results |
| 3 | Match real world | "Live preview" vs "transcribe after" labels (not "chunked"/"single clip") |
| 4 | User control & freedom | Blob retention enables re-transcription with different models |
| 5 | User control & freedom | Editable transcripts before saving |
| 6 | Consistency | Inline settings panel, no trip to Settings page |
| 7 | Error prevention | Confirmation on Clear All, undo toast on single delete |
| 8 | Recognition over recall | Direct settings access via gear icon, not "go to Settings" |
| 9 | Flexibility & efficiency | Keyboard shortcuts for record, transcribe, copy |
| 10 | Flexibility & efficiency | Copy-to-clipboard on every result card |
| 11 | Aesthetic/minimalist | Consolidated config display, no redundant tags |
| 12 | Error recovery | Per-card error + retry, model load error with clear empty state |

## Stretch Goals (not in v1)

- **Diff mode** — toggle to highlight textual differences between model outputs
- **Audio waveform visualization** — replace simple level meter with waveform display
- **Batch file upload** — drag-drop multiple files for bulk comparison
