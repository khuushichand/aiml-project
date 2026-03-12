# TTS "Compose & Compare" Full Redesign

**Date**: 2026-03-07
**Status**: Design
**Builds on**: `2026-03-06-tts-listen-tab-ux-redesign.md` (two-zone layout, provider strip, inspector panel)
**Scope**: Full TTS experience redesign — page structure, render strips, voice picker, unified player

---

## Problem Statement

The Speech Playground TTS experience (`SpeechPlaygroundPage.tsx`, 2,839 lines) has several UX issues grounded in Nielsen's 10 usability heuristics:

1. **Inconsistent playback** (H4: Consistency) — Browser TTS uses Web Speech API controls; server TTS uses HTML5 `<audio>`. Different UI for the same action.
2. **Provider switching confusion** (H6: Recognition over recall) — Changing providers reveals/hides different controls unpredictably. Users must remember which fields belong to which provider.
3. **No comparison capability** (H7: Flexibility & efficiency) — No way to A/B test voices, models, or providers. Users must generate, listen, change settings, regenerate, and try to remember the previous result.
4. **19 adapters, 4 exposed** (H8: Minimalist design, inverted) — The backend supports Kokoro, Higgs, Chatterbox, VibeVoice, ElevenLabs, OpenAI, and 13 more, but the UI only exposes 4 provider buckets.
5. **Unsurfaced backend features** — Voice upload, voice preview, TTS history, async jobs, word-level alignment metadata are all available via API but not in the UI.
6. **Settings form overload** (H8: Aesthetic & minimalist design) — 1,000+ lines of settings compete for attention on the same page.

## Target Users

Design uses progressive disclosure to serve three personas:
- **General users**: Type text, click play. Minimal cognitive load.
- **Content creators**: Batch generation, export, quality comparison.
- **Developers/tinkerers**: Full provider visibility, parameter tuning, A/B testing.

## Design: Compose & Compare

### Core Concept

The text editor is the primary surface. Audio outputs appear as **Render Strips** below the editor — self-contained cards, each representing one generation with its own provider/voice/settings. Comparison is structural: having two strips *is* comparison. No special mode needed.

### Page Structure

Single `/speech` route with top-level tabs: **TTS | STT | Roundtrip**

TTS tab layout:

```
+----------------------------------------------+
| Document Toolbar                              |
| [Voice: kokoro/af_heart ▾] [Preset: Balanced]|
| [+ Add Render]  [History]  [⚙ Settings]      |
+----------------------------------------------+
|  Text Editor (hero element)                   |
|  +------------------------------------------+|
|  | [Auto-sizing textarea]                    ||
|  | 142/8000 chars · ~9s estimated            ||
|  +------------------------------------------+|
|                                               |
|  Render Strips                                |
|  +------------------------------------------+|
|  | A: [kokoro] [af_heart] [mp3] [1.0x]      ||
|  |    [Edit] [✕]                             ||
|  |    [========waveform=======] 0:12/0:45    ||
|  |    [⏮][▶ Play][⏭] ───●───── [⬇ Download]||
|  +------------------------------------------+|
|  | B: [higgs] [en_speaker_0] [wav] [0.9x]   ||
|  |    [Edit] [✕]                             ||
|  |    [========waveform=======] 0:08/0:38    ||
|  |    [⏮][▶ Play][⏭] ───●───── [⬇ Download]||
|  +------------------------------------------+|
|                                               |
| [▶ Generate] [■ Stop] [▶▶ Play All]          |
+----------------------------------------------+
```

Drawers (right side, opened on demand):
- **Settings Drawer** — reuses `TtsInspectorPanel` with Voice, Output, Advanced tabs
- **History Drawer** — past generations with search, filter, favorites

### Component: Render Strip

Each strip is a self-contained card with five states:

| State | Visual |
|-------|--------|
| `idle` | Config tags + "Click Generate to synthesize" |
| `generating` | Progress bar (or job step indicator for long text) |
| `ready` | Waveform + playback controls + download |
| `playing` | Animated waveform, highlighted play button |
| `error` | Error message + Retry button |

**Interactions:**
- Config tags are clickable — clicking `[kokoro]` opens the voice picker pre-filtered
- `[Edit]` opens the settings drawer pre-filled with this strip's config
- `[✕]` removes the strip with an undo toast (H3: User control & freedom)
- Only one strip plays at a time — starting one pauses others
- `[Play All]` plays strips sequentially with a 1-second pause between them

### Component: Voice Picker Modal

Replaces the current per-provider voice/model selection with a unified modal:

```
+----------------------------------------------------------+
|  Choose a Voice                              [✕ Close]   |
+----------------------------------------------------------+
|  [🔍 Search voices...]                                   |
|  Recent: [af_heart] [alloy] [en_speaker_0]               |
+----------------------------------------------------------+
|  ▾ Local Engines                                         |
|    ● Kokoro (12 voices)              [healthy]           |
|      af_heart [▶]  |  af_bella [▶]  |  am_adam [▶]      |
|    ● Higgs (8 voices)                [healthy]           |
|      en_speaker_0 [▶]  |  en_speaker_1 [▶]              |
|    ○ Chatterbox                       [offline]          |
|  ▾ Cloud Providers                                       |
|    ● OpenAI (6 voices)                                   |
|      alloy [▶]  |  echo [▶]  |  nova [▶]                |
|    ● ElevenLabs (50+ voices)                             |
|  ▾ Custom Voices                                         |
|    my_cloned_voice [▶]  |  [+ Upload New]               |
+----------------------------------------------------------+
```

**Key behaviors:**
- `[▶]` preview buttons call `/api/v1/audio/voices/{voice_id}/preview` — audio plays inline within the picker
- Health status per provider from circuit breaker state (green dot / dimmed "offline")
- Search filters across all providers simultaneously
- Recent voices (last 5 used) pinned at top
- Selecting a voice auto-selects its provider — no two-step "pick provider, then pick voice"
- Provider capability icons: streaming, cloning, emotion, SSML
- Custom voices section has inline upload via existing `VoiceCloningManager`

### Component: Unified Audio Player

Eliminates the H4 (Consistency) violation of different playback UIs per provider:

- Single player component used in all render strips
- For server providers: wraps HTML5 audio with custom waveform (reuses `WaveformCanvas`) + controls
- For browser TTS: synthesizes via Web Speech API, maps events to same progress/play/pause interface
- Consistent controls: play/pause, seek via waveform click, time display, download
- Graceful degradation: if waveform data unavailable, shows animated progress bar with same controls

### Progressive Disclosure

| Level | What's visible | How to reach it |
|-------|---------------|-----------------|
| 0 — Just play | Text editor + toolbar (default voice) + action bar | Default state |
| 1 — Customize | Click toolbar chip → settings drawer opens | 1 click |
| 2 — Compare | Click "+ Add Render" → voice picker → second strip | 2 clicks |
| 3 — Advanced | Settings drawer → Advanced tab (SSML, emotion, normalization, voice roles, async jobs) | 3 clicks |
| 4 — Voice mgmt | Voice picker → Custom Voices → upload/clone | On demand |

### Backend Feature Surfacing

| Backend Feature | Where it appears |
|----------------|-----------------|
| All 19 TTS adapters | Voice Picker modal, grouped by Local/Cloud |
| Voice preview API | `[▶]` button on each voice in the picker |
| Custom voice upload | "Custom Voices" section in picker + `VoiceCloningManager` |
| Voice encode/clone | Advanced tab in settings drawer |
| TTS history | History drawer (right side) |
| Async TTS jobs | Strip progress indicator for text > 2000 chars |
| Word-level alignment | Opt-in: toggle on strip header highlights words in editor during playback |
| Provider health | Colored dot per provider in voice picker |
| Streaming | Progressive waveform drawing as audio arrives |

### Heuristic Coverage

| # | Heuristic | How addressed |
|---|-----------|---------------|
| 1 | Visibility of system status | Strip states, provider health dots, char count, estimated duration, waveform progress |
| 2 | Match system & real world | Voice names + preview (not IDs), "Local Engines"/"Cloud Providers" grouping |
| 3 | User control & freedom | Undo on strip removal, history drawer, explicit generate, editable config |
| 4 | Consistency & standards | Unified audio player for all providers, consistent strip cards |
| 5 | Error prevention | Char limit warning at 2000, explicit generate for all text, dimmed offline providers |
| 6 | Recognition over recall | Recent voices pinned, config shown as tags on strips, voice preview |
| 7 | Flexibility & efficiency | Ctrl+Enter to generate, presets, "+ Add Render", clickable config tags |
| 8 | Aesthetic & minimalist design | Only editor + toolbar visible by default; settings/history in drawers |
| 9 | Help users recover | Error state on strips with retry, toast with undo on deletion, provider retry |
| 10 | Help & documentation | Tooltips on capability icons, estimated duration, char count guidance |

### Relationship to Prior Designs

This design extends `2026-03-06-tts-listen-tab-ux-redesign.md`:
- **Keeps**: Two-zone concept (workspace + inspector), provider strip, sticky action bar, inspector panel tabs
- **Adds**: Render strips (multi-generation), voice picker modal, unified audio player, comparison flow
- **Changes**: Action bar includes "Add Render" and "Play All"; workspace zone contains render strips instead of single waveform

The STT tab follows `2026-03-06-stt-playground-comparison-first-redesign.md` unchanged.

### Existing Components to Reuse

| Component | File | Reuse plan |
|-----------|------|------------|
| `TtsProviderStrip` | `Speech/TtsProviderStrip.tsx` | Becomes document toolbar |
| `TtsStickyActionBar` | `Speech/TtsStickyActionBar.tsx` | Becomes action bar with added "Add Render" / "Play All" |
| `TtsInspectorPanel` | `Speech/TtsInspectorPanel.tsx` | Settings drawer shell (reuse as-is) |
| `TtsVoiceTab` | `Speech/TtsVoiceTab.tsx` | Inspector voice tab (refactor to support per-strip config) |
| `TtsOutputTab` | `Speech/TtsOutputTab.tsx` | Inspector output tab |
| `TtsAdvancedTab` | `Speech/TtsAdvancedTab.tsx` | Inspector advanced tab |
| `WaveformCanvas` | `Common/WaveformCanvas.tsx` | Waveform in each render strip |
| `TtsJobProgress` | `Common/TtsJobProgress.tsx` | Progress indicator in generating strips |
| `VoiceCloningManager` | `TTS/VoiceCloningManager.tsx` | Custom voices section in voice picker |
| `CharacterProgressBar` | `Common/CharacterProgressBar.tsx` | Char count in text editor |
| `LongformDraftEditor` | `Common/LongformDraftEditor.tsx` | Advanced text editing mode |
| `useTtsPlayground` | `hooks/useTtsPlayground.tsx` | Evolve to multi-strip state management |
| `useTtsProviderData` | `hooks/useTtsProviderData.ts` | Provider/voice data fetching |
| `useStreamingAudioPlayer` | `hooks/useStreamingAudioPlayer.ts` | Streaming playback per strip |

### New Components to Build

1. **`RenderStrip`** — Self-contained card: config tags + unified player + waveform + download
2. **`VoicePickerModal`** — Provider-grouped voice catalog with search, preview, recent, custom upload
3. **`UnifiedAudioPlayer`** — Normalizes browser TTS and server TTS behind common play/pause/seek/progress interface
4. **`useMultiRenderState`** — Hook managing array of render strip states with independent generation
