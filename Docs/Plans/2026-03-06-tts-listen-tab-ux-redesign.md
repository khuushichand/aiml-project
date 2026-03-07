# TTS Listen Tab UX Redesign

**Date**: 2026-03-06
**Status**: Design Approved
**Scope**: Listen (TTS) tab within the Speech Playground (`/tts`, `/speech?mode=listen`)

---

## Problem Statement

The Listen tab in the Speech Playground presents all configuration and interaction in a single vertical scroll. This creates several usability problems grounded in Nielsen Norman Group heuristics:

1. **Play button below the fold** — the primary action requires scrolling past configuration (Fitts's Law, Visibility of system status)
2. **Information overload** — provider panel, presets, text input, split controls, advanced controls, voice cloning, streaming status, waveform, segments, and history all compete for attention (Aesthetic & minimalist design)
3. **Dual configuration surfaces** — Settings page and playground both write to the same storage keys with different save patterns, creating confusion about which is authoritative (Consistency and standards)
4. **No voice preview** — users must generate full audio to evaluate a voice (User control and freedom)
5. **Segment navigation is opaque** — numbered buttons with no text preview (Match between system and real world)
6. **Three generation modes with unclear selection** — standard, streaming, TTS job are controlled by scattered toggles (Recognition rather than recall)
7. **Preset buttons unexplained** — no way to see what a preset changes before applying it (Help and documentation)

## Design: Two-Zone Layout

Split the Listen tab into two zones: a focused Workspace (always visible) and a collapsible Inspector Panel (configuration).

### Overall Layout

```
+-------------------------------------------+-------------------+
|  ZONE 1: WORKSPACE                        |  ZONE 2: INSPECTOR|
|                                           |  (collapsible)    |
|  [Provider Strip: model/voice/fmt/preset] |  [Voice|Output|Adv]|
|  [Text Input + char progress bar]         |  (tab content)    |
|  [Stats line]                             |                   |
|  [Streaming/Job status — when active]     |                   |
|  [Waveform — when audio exists]           |                   |
|  [Segment nav — when >1 segment]          |                   |
+-------------------------------------------+-------------------+
|  [Play] [Stop] [Download v]    status  [gear]                 |
+---------------------------------------------------------------+
|  Speech History                                               |
+---------------------------------------------------------------+
```

### Responsive Behavior

| Viewport | Zone 2 behavior |
|----------|----------------|
| Desktop >= 1024px | Side panel, ~320px fixed width, slides in/out |
| Tablet 768-1023px | Right-edge drawer overlay (Ant Design Drawer) |
| Mobile <768px | Full-screen drawer overlay |

Panel state (open/closed + active tab) persisted to storage.

---

## Zone 1: The Workspace

### Provider Strip

Single horizontal line: provider icon, model, voice, format, speed as clickable Tags. Clicking any label opens Zone 2 with that field focused. Preset selector (Fast/Balanced/Quality) inline. Gear icon toggles Zone 2.

Tooltip on each preset option shows what it changes (e.g., "Fast: streaming on, mp3, punctuation split, 1.2x").

### Text Input

Standard textarea (or LongformDraftEditor when draft mode is active in Zone 2).

Character progress bar at bottom of textarea:
- Green: 0-2,000 chars
- Amber: 2,000-6,000 chars
- Red: 6,000-8,000 chars
- Shows `{count} / 8,000 chars` right-aligned

"Insert sample text" button below input.

### Stats Line

`42 words . 3 segments (punctuation) . Est. ~8s`

Segment count is clickable — opens popover with segment text previews.

### Streaming / Job Status

Appears between text area and waveform only when active.

Streaming: `[blue dot] Streaming... 12 chunks . 48.2 KB received`
TTS Job: Progress bar + step indicator using existing TtsJobProgress component.
Errors show inline with Retry button.

### Waveform + Segments

Existing WaveformCanvas, shown only after audio generation.

Segment buttons show truncated text preview (first ~25 chars) instead of just numbers. Active segment highlighted. Horizontal scroll when many segments. Hidden when single segment.

### Sticky Action Bar

`sticky bottom-0` with background and top border.

Contents: Play (primary), Stop (default), Download (dropdown: current segment / all), streaming status dot, gear toggle for Zone 2.

Disabled-state helper text shown inline below buttons.

---

## Zone 2: The Inspector Panel

Panel chrome: title bar with close button, three tabs. Changes take effect immediately (no Save button) — writes to same storage keys as Settings page. Last-touched surface wins.

### Tab 1: Voice

What voice speaks.

- Provider selector
- Model selector
- Voice selector with **Preview button** (synthesizes fixed short phrase, plays immediately, no history entry)
- Language selector (when provider supports it)
- Emotion preset + intensity slider (when provider supports emotion control)
- Voice Roles: checkbox "Use multi-voice narration" with expandable voice role cards (tldw only)

Provider-conditional rendering:
- browser: Voice only
- openai: Model + Voice
- elevenlabs: API key status + Model + Voice
- tldw: Full set

### Tab 2: Output

How audio is produced and delivered.

- Format selector
- Synthesis speed slider (0.25-4.0x) with numeric display
- Playback speed slider (0.25-2.0x) with numeric display
- Response splitting selector (None/Punctuation/Paragraph)
- Streaming toggle with description (disabled when format unsupported, with tooltip)
- Smart normalization card with sub-toggles (Units, URLs, Emails, Phone, Pluralization)

### Tab 3: Advanced

Power-user features.

- Draft editor toggle with description
- TTS Job toggle with description
- SSML toggle
- Remove `<think>` tags toggle
- Voice Cloning Manager access (button opening existing component)
- Preset detail reference (read-only table showing what each preset changes)

---

## Error Handling

Errors appear where the user is looking, not where the problem originated.

| Scenario | Behavior |
|----------|----------|
| TTS disabled | Sticky bar always visible — helper text explains |
| No text | Helper text in sticky bar: "Enter text to enable Play" |
| Provider not configured | Red dot on gear + banner at top of Zone 1 with configure link |
| Catalog load failure | Amber dot on gear + inline warning in provider strip with Retry |
| Generation failure | Toast for transient + inline error with Retry between text and waveform |
| Streaming error | Inline in streaming status area with Retry button |
| Format unsupported | Pre-flight check on Play — inline error with auto-switch action |
| Char limit exceeded | Red progress bar + Play disabled + helper text |

Gear button badge: gray dot (closed, no issues), red (config error), amber (warning), none (panel open).

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl/Cmd + Enter | Play (or Stop if playing) — when text area focused |
| Escape | Stop playback |
| Ctrl/Cmd + . | Toggle Zone 2 panel |

Shortcuts shown as tooltips on relevant buttons.

---

## Accessibility

- Zone 2 panel: `role="complementary"`, `aria-label="TTS Configuration"`
- Drawer variant: `role="dialog"`, `aria-modal="true"`, focus trap
- Sticky bar: `role="toolbar"`, `aria-label="Playback controls"`
- Provider strip labels: `aria-live="polite"` for screen reader announcements on change
- Character progress bar: `role="progressbar"`, `aria-valuenow`, `aria-valuemax="8000"`
- Segment buttons: `role="tablist"` / `role="tab"` with `aria-selected`
- Streaming/job status: `aria-live="polite"` region
- Focus management: Zone 2 open focuses first element; close returns focus to gear button; generation complete focuses Play/Stop

---

## Component Architecture

### Reused as-is
- WaveformCanvas.tsx
- TtsJobProgress.tsx
- LongformDraftEditor.tsx
- VoiceCloningManager.tsx
- useTtsPlayground hook
- useStreamingAudioPlayer hook
- useTtsProviderData hook
- tts.ts settings service

### Restructured
- SpeechPlaygroundPage.tsx — remains container, JSX reorganized into zones

### Replaced
- TtsProviderPanel.tsx — replaced by TtsProviderStrip (compact)

### Retired from playground
- TTSModeSettings.tsx — kept only for /settings/speech page

### New components
- TtsProviderStrip.tsx (~80 lines) — compact config summary with clickable labels
- TtsInspectorPanel.tsx (~120 lines) — Zone 2 container, tabs, open/close
- TtsVoiceTab.tsx (~250 lines) — provider, model, voice, preview, emotion, roles
- TtsOutputTab.tsx (~200 lines) — format, speeds, splitting, streaming, normalization
- TtsAdvancedTab.tsx (~150 lines) — draft editor, TTS job, SSML, reasoning, cloning
- TtsStickyActionBar.tsx (~100 lines) — Play, Stop, Download, status, gear toggle
- CharacterProgressBar.tsx (~30 lines) — colored bar with count
- VoicePreviewButton.tsx (~60 lines) — synthesize and play preview phrase

### State management
No new stores. Existing useStorage + useState pattern.

New lifted state in SpeechPlaygroundPage:
```typescript
const [inspectorOpen, setInspectorOpen] = useStorage<boolean>("ttsInspectorOpen", false)
const [inspectorTab, setInspectorTab] = useStorage<"voice" | "output" | "advanced">("ttsInspectorTab", "voice")
const [inspectorFocusField, setInspectorFocusField] = useState<string | null>(null)
```

### Settings relationship
- Settings page (/settings/speech): writes defaults with Save button (unchanged)
- Playground Zone 2: writes immediately on change to same keys (no Save button)
- Last-touched surface wins — no dual-config confusion

---

## Migration Risk

**Low risk**: All hooks/services unchanged. Components relocated, not rewritten.

**Medium risk**: SpeechPlaygroundPage render (~800 lines JSX) split across 6 components. Mitigation: purely structural refactor, same props.

**Mitigation for auto-persist**: Debounce writes by 300ms so rapid tabbing through fields coalesces.

**Not changing**: STT tab, Round-trip mode, History section, backend API calls, generation/streaming/job logic.
