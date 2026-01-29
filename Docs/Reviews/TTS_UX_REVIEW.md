# TTS UX Review - Speech Playground

**Review Date:** 2026-01-27
**Reviewer Role:** Senior UX/HCI Design Specialist
**Component:** Speech Playground TTS Page (`/options/speech`, `/options/tts`)

---

## Executive Summary

The Speech Playground provides a functional TTS experience with browser, OpenAI, ElevenLabs, and tldw (Kokoro) providers. However, significant server-side capabilities remain unexposed in the UI, and several usability issues impact user efficiency.

**Key Findings:**
- Only 4 of 16 server-side TTS providers are exposed
- Voice cloning infrastructure exists but has no UI
- Critical features (emotion control, format selection, normalization) are hidden
- Settings complexity could overwhelm new users
- History/clips management is functional but could be more discoverable

---

## PART A: Server Capabilities Audit

### A1. Provider Coverage (16 server providers → 4 UI exposed)

| Provider | Server Status | UI Exposed | Issue |
|----------|---------------|------------|-------|
| OpenAI | ✅ Enabled | ✅ Yes | Model selection (tts-1 vs tts-1-hd) available |
| Kokoro | ✅ Enabled (default) | ✅ Via "tldw" | **Confusing naming** - users don't know Kokoro is the engine |
| ElevenLabs | ⚠️ Disabled by default | ✅ Yes | API key setup flow is clear |
| Browser | N/A (client-side) | ✅ Yes | Should indicate no download capability |
| PocketTTS | ❌ Disabled | ❌ No | Voice cloning capable - hidden appropriately |
| Higgs | ❌ Disabled | ❌ No | Multi-lingual + cloning - hidden appropriately |
| Chatterbox | ❌ Disabled | ❌ No | **Emotion control** - valuable if enabled |
| VibeVoice | ❌ Disabled | ❌ No | Background music, singing - niche |
| VibeVoice Realtime | ❌ Disabled | ❌ No | Low-latency streaming - niche |
| NeuTTS | ❌ Disabled | ❌ No | Instant voice cloning |
| Dia | ❌ Disabled | ❌ No | Multi-speaker dialogue |
| Qwen3-TTS | ❌ Disabled | ❌ No | Voice cloning + emotion + voice design |
| LuxTTS | ❌ Disabled | ❌ No | ZipVoice cloning |
| IndexTTS2 | ❌ Disabled | ❌ No | Zero-shot expressive |
| Supertonic/2 | ❌ Disabled | ❌ No | User-supplied ONNX models |
| EchoTTS | ❌ Disabled | ❌ No | CUDA-only voice cloning |

**Recommendations:**
1. **Rename "tldw" to "Kokoro (Local)"** to clarify the actual engine
2. **Add "Browser (Limited)" badge** to indicate no download support
3. Disabled-by-default providers should remain hidden - correct current approach

### A2. Voice Cloning (8 providers support it)

| Capability | Server | UI | Gap |
|------------|--------|-----|-----|
| Upload voice sample | `POST /audio/voices/upload` | ❌ Missing | **Critical gap** |
| Encode for provider | `POST /audio/voices/encode` | ❌ Missing | Needed for workflow |
| List custom voices | `GET /audio/voices` | ❌ Missing | Needed for selection |
| Delete voice | `DELETE /audio/voices/{id}` | ❌ Missing | Needed for management |
| Preview custom voice | `POST /audio/voices/{id}/preview` | ❌ Missing | Nice to have |
| Capability flag display | `supports_voice_cloning` | ✅ Tag shown | Works correctly |

**Current State:** The `TtsProviderPanel` shows a "Voice cloning" tag when the provider supports it, but there's no actual UI to use the feature.

**Recommendation:** Add a dedicated voice cloning section for supported providers with:
- Upload interface with duration/format requirements per provider
- Custom voice dropdown in voice selection
- Preview/delete functionality

### A3. Audio Output Formats

| Format | Server Support | UI Exposed | Notes |
|--------|----------------|------------|-------|
| mp3 | ✅ | ✅ Settings | Default |
| wav | ✅ | ✅ Settings | Lossless option |
| opus | ✅ | ✅ Settings | Efficient codec |
| aac | ✅ | ✅ Settings | Good compatibility |
| flac | ✅ | ✅ Settings | Lossless |
| pcm | ✅ | ✅ Settings | **Should hide** - raw, non-standard |
| ogg | ✅ | ❌ Hidden | Could add |
| webm | ✅ | ❌ Hidden | Could add |
| ulaw | ✅ | ❌ Hidden | **Keep hidden** - telephony specific |

**Current State:** 6 formats available in TTSModeSettings. Format selection happens at settings level, not download time.

**Issues:**
1. No format selection at download time
2. PCM exposed to non-technical users
3. Format trade-offs not explained

**Recommendation:**
- Hide PCM from default format list (advanced users can enable)
- Add tooltip explaining format trade-offs (size vs quality vs compatibility)
- Consider adding format selection at download time for power users

### A4. Text Normalization Options

| Option | Server Support | UI Exposed |
|--------|----------------|------------|
| normalize (general) | ✅ | ❌ Hidden |
| unit_normalization ("10KB" → "10 kilobytes") | ✅ | ❌ Hidden |
| url_normalization | ✅ | ❌ Hidden |
| email_normalization | ✅ | ❌ Hidden |
| phone_normalization | ✅ | ❌ Hidden |

**Current State:** No normalization controls in UI. Server applies defaults.

**Recommendation:** Add a single "Smart normalization" toggle that enables all options when on. For power users, provide an expandable "Advanced normalization" section.

### A5. Speed Control

| Aspect | Server | UI | Issue |
|--------|--------|-----|-------|
| Range | 0.25x - 4.0x | 0.25x - 2.0x (Settings) | **UI limits to 2x** |
| Default | 1.0x | 1.0x | ✓ Correct |
| Precision | Continuous | Slider | ✓ Appropriate |

**Issues:**
1. Server supports 4.0x but UI caps at 2.0x
2. Potential confusion: Is speed for generation or playback?

**Recommendation:**
- Extend UI range to 4.0x (or 3.0x compromise)
- Label clearly: "Generation Speed" vs "Playback Speed"

### A6. Streaming Capabilities

| Capability | Server | UI Support |
|------------|--------|------------|
| HTTP chunked streaming | ✅ `stream: true` | ✅ Used |
| WebSocket TTS | ✅ `/stream/tts` | ❌ Not used |
| WebSocket Realtime | ✅ `/stream/tts/realtime` | ❌ Not used |
| Progress indication | N/A | ⚠️ Limited |

**Current State:** UI uses HTTP streaming. Progress shown via "Generating..." state but no chunk-level progress.

**Recommendation:**
- Add visible streaming progress (e.g., "Receiving audio..." with animated indicator)
- WebSocket streaming could enable lower latency but HTTP is adequate for current use cases

### A7. Emotion & Expression Control

| Provider | Server Support | UI Exposed |
|----------|----------------|------------|
| Chatterbox | ✅ emotion, emotion_intensity | ❌ Hidden |
| IndexTTS2 | ✅ emo_audio_reference, emo_alpha, emo_text | ❌ Hidden |
| ElevenLabs | ✅ stability, similarity_boost, style | ❌ Hidden |
| VibeVoice | ✅ vibe, vibe_intensity, enable_music | ❌ Hidden |
| Qwen3-TTS | ✅ Full voice design | ❌ Hidden |

**Current State:** No emotion controls exposed. Server capabilities unused.

**Recommendation:**
- Show emotion/style controls **only when relevant provider selected**
- ElevenLabs: Add stability/similarity sliders
- For other providers: Surface when they become enabled

### A8. Language Support

| Aspect | Server | UI | Issue |
|--------|--------|-----|-------|
| `lang_code` parameter | ✅ Supported | ⚠️ Implicit | No explicit selector |
| Per-provider languages | ✅ Defined | ❌ Not shown | Users can't see options |
| Auto-detection | ✅ From voice name | ✅ Works | Adequate for now |

**Current State:** Language is determined by voice selection. No explicit language selector.

**Recommendation:**
- For multilingual providers (ElevenLabs, Higgs), show available languages
- Filter voice list by selected language
- Low priority if most users use English

### A9. Advanced Features Matrix

| Feature | Server | UI Recommendation |
|---------|--------|-------------------|
| SSML input | ✅ Flag supported | ✅ Toggle exists - adequate |
| Phoneme overrides | ⚠️ Provider-specific | Keep hidden |
| Voice design (Qwen3) | ✅ Full API | Keep hidden until Qwen3 enabled |
| Speech-to-Speech | ✅ Full endpoint | Roundtrip mode should use this |
| Audio tokenizer | ✅ encode/decode | Developer-only - hide |

---

## PART B: Current UI Feature Evaluation

### B1. Text Input Area

| Feature | Status | Notes |
|---------|--------|-------|
| Textarea | ✅ Works | Adequate size |
| Sample text insertion | ❓ Not found | Missing - would help onboarding |
| Character/word count | ❌ Missing | Should add |
| Text segmentation preview | ❌ Missing | Would help understand chunking |

**Issues:**
1. No character limit indicator (important for some providers)
2. No preview of how text will be segmented
3. No sample text for quick testing

**Severity:** Minor

### B2. Provider Configuration Panel

| Feature | Status | Notes |
|---------|--------|-------|
| Provider selector | ✅ 4 options | Clear dropdown |
| Model selection | ✅ Per provider | Works well |
| Voice selection | ✅ With preview | Good - shows language |
| API key setup | ✅ ElevenLabs, OpenAI | Clear flow with test button |
| TtsProviderPanel capabilities | ⚠️ Info overload | Shows many capability tags |

**Issues:**
1. `TtsProviderPanel` shows all capability tags which may overwhelm
2. "tldw" name is confusing

**Severity:** Minor

### B3. Playback Controls

| Feature | Status | Notes |
|---------|--------|-------|
| Play/Stop | ✅ Responsive | Works well |
| Speed control | ✅ Slider | Works (playback rate) |
| Waveform visualization | ✅ Functional | Real-time FFT, looks good |
| Segment navigation | ⚠️ Basic | Button per segment |
| Time display | ✅ currentTime/duration | Accurate |

**Issues:**
1. Segment navigation could show segment text preview
2. No keyboard shortcuts for playback control

**Severity:** Minor

### B4. Output Actions

| Feature | Status | Notes |
|---------|--------|-------|
| Download current segment | ✅ Works | Per-segment download |
| Download all segments | ✅ Works | Combines MP3 only |
| Save to clips/notes | ✅ TtsClipsDrawer | Via drawer |
| Format selection for download | ❌ Missing | Downloads in generation format |

**Issues:**
1. "Download All" only works for MP3 segments
2. No format conversion at download time
3. "Download All" button discoverability could improve

**Severity:** Minor

### B5. History Panel (TtsClipsDrawer)

| Feature | Status | Notes |
|---------|--------|-------|
| Filter by type | ⚠️ Basic | All/STT/TTS tabs |
| Search functionality | ❌ Missing | Cannot search clip text |
| Per-item actions | ✅ Play/Download/Delete | Good coverage |
| Metadata display | ✅ Complete | Date, provider, voice shown |
| Mixed STT/TTS | ✅ Filtered tabs | Works well |

**Issues:**
1. No text search within clips
2. Limit of 30 clips may be too low for power users
3. No export all functionality

**Severity:** Minor

### B6. Settings Integration (TTSModeSettings)

| Setting | Status | Clarity |
|---------|--------|---------|
| TTS enabled toggle | ✅ | Clear |
| Auto-play toggle | ✅ | Clear |
| Provider selection | ✅ | Clear |
| Playback speed | ✅ | **Ambiguous** - generation or playback? |
| SSML toggle | ⚠️ | Hidden in settings - low discoverability |
| Remove reasoning tags | ⚠️ | **Purpose unclear** to users |
| Response splitting | ✅ | Options are clear |

**Issues:**
1. "Remove reasoning tags" needs explanation
2. 13+ options may overwhelm first-time users
3. Settings scattered between in-page and settings panel

**Severity:** Major

---

## PART C: Task Flow Analysis

### C1. Quick Synthesis (Happy Path)

**Flow:** Enter text → Generate → Play

| Step | Clicks | Notes |
|------|--------|-------|
| Enter text | 1 | Click textarea |
| Generate | 1 | Click Speak button |
| Play | 0 | Auto-plays if enabled, otherwise 1 click |
| **Total** | 2-3 | ✓ Efficient |

**Assessment:** Happy path is well-optimized. Sensible defaults applied.

**Issue:** No visible generation progress beyond loading state.

### C2. Provider Comparison (A/B Testing)

**Flow:** Same text, multiple voices/providers

| Step | Current UX | Friction |
|------|------------|----------|
| Generate with Provider A | ✅ Easy | - |
| Switch provider | ✅ Dropdown | - |
| Regenerate | ✅ Easy | - |
| Compare outputs | ⚠️ Manual | Must play sequentially |
| Side-by-side | ❌ Not possible | **Missing feature** |

**Issues:**
1. No side-by-side comparison view
2. History helps but doesn't enable direct comparison
3. Cannot play two clips simultaneously for comparison

**Severity:** Minor (enhancement request)

### C3. Voice Cloning Workflow

**Flow:** Upload sample → Configure → Generate with cloned voice

| Step | Status | Notes |
|------|--------|-------|
| Upload sample | ❌ **Not possible** | No upload UI |
| Configure voice | ❌ **Not possible** | No management UI |
| Select cloned voice | ❌ **Not possible** | No custom voices in dropdown |
| Generate | N/A | Workflow broken |

**Assessment:** **Critical gap** - Server supports full voice cloning CRUD but UI has no access.

**Severity:** Major (if voice cloning is a target feature)

### C4. Batch Export

**Flow:** Generate multiple segments → Download all

| Step | Current UX | Issues |
|------|------------|--------|
| Generate segments | ✅ Auto-segments | Works well |
| Download All | ⚠️ Discoverable | Only combines MP3 |
| Format selection | ❌ Not available | Uses generation format |
| Progress indication | ❌ None | For large batches |

**Issues:**
1. Mixed format segments can't be combined
2. No progress for large batch downloads
3. Button labeling could be clearer

**Severity:** Minor

### C5. Settings Recovery

**Flow:** User configured provider → returns later

| Step | Current UX | Notes |
|------|------------|-------|
| Settings persisted | ✅ localStorage | Works |
| Config visible at glance | ⚠️ Partial | Must check settings panel |
| Quick provider switch | ✅ In-page dropdown | Works |

**Issues:**
1. Current configuration not summarized on main page
2. User must open settings to see full config

**Severity:** Minor

---

## PART D: Evaluation Criteria Assessment

### D1. Information Architecture

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Three-mode structure | ⚠️ Questionable | "Roundtrip" may confuse users |
| Settings location | ⚠️ Split | Some in-page, some in panel |
| Provider config | ✅ Manageable | 4 providers is digestible |

**Issues:**
1. "Roundtrip" mode concept not immediately clear
2. Settings split between multiple locations

**Recommendation:** Consider renaming "Roundtrip" to "Speech-to-Speech" or similar

### D2. Progressive Disclosure

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Basic TTS zero-config | ✅ Works | Browser provider works OOTB |
| Advanced features hidden | ✅ Mostly | SSML, format in settings |
| Clear advanced mode | ❌ Missing | Options accumulate |

**Recommendation:** Add "Advanced Options" collapsible section

### D3. Error Handling & Feedback

| Scenario | Current UX | Assessment |
|----------|------------|------------|
| Invalid API key | ✅ Clear error | Good |
| Provider unavailable | ⚠️ Generic error | Could be more specific |
| Rate limited | ❓ Not tested | Should show retry time |
| Generation progress | ⚠️ Basic | "Generating..." only |
| Failed recovery | ⚠️ Manual retry | No auto-retry option |

**Severity:** Minor

### D4. Accessibility

| Aspect | Status | Notes |
|--------|--------|-------|
| Keyboard navigation | ⚠️ Partial | Not fully tested |
| Screen reader support | ❓ Unknown | Needs audit |
| High contrast | ❓ Unknown | Depends on theme |
| Touch targets | ✅ Adequate | Ant Design defaults |

**Recommendation:** Conduct dedicated accessibility audit

### D5. Cognitive Load

| Aspect | Assessment | Count |
|--------|------------|-------|
| Provider options | ✅ Low | 4 options |
| Settings toggles | ⚠️ High | 13+ options |
| History panel | ⚠️ Medium | Mixed content |
| Visible controls | ⚠️ Medium | Many simultaneous |

**Issues:**
1. Settings panel has too many ungrouped options
2. All controls visible simultaneously

---

## Issue Table Summary

| ID | Location | Problem | Heuristic | Severity | Recommendation |
|----|----------|---------|-----------|----------|----------------|
| 1 | Provider naming | "tldw" doesn't indicate Kokoro engine | Recognition over recall | Major | Rename to "Kokoro (Local)" |
| 2 | Voice cloning | Server supports full CRUD, UI has none | Feature parity | Major | Add voice upload/management UI |
| 3 | Settings panel | 13+ options ungrouped | Aesthetic & minimal | Major | Group into Basic/Advanced sections |
| 4 | Speed range | UI caps at 2x, server supports 4x | Flexibility | Minor | Extend slider to 4x |
| 5 | Text normalization | 5 server options unexposed | Feature parity | Minor | Add "Smart normalization" toggle |
| 6 | Emotion control | Multiple providers support it, UI doesn't | Feature parity | Minor | Add when provider selected supports it |
| 7 | Character count | No text length indicator | Visibility | Minor | Add character/word count |
| 8 | Format at download | Can only download in generation format | User control | Minor | Add format conversion option |
| 9 | Browser provider | No indication of limited functionality | Help & documentation | Minor | Add "(Limited)" badge |
| 10 | Roundtrip naming | "Roundtrip" concept unclear | Match real world | Minor | Rename to "Speech-to-Speech" |
| 11 | Remove reasoning tags | Setting purpose unclear | Help & documentation | Minor | Add tooltip explaining purpose |
| 12 | Playback vs generation speed | Ambiguous which is controlled | Visibility | Minor | Label clearly which speed |
| 13 | Clips search | Cannot search clip text content | Flexibility | Minor | Add search functionality |
| 14 | PCM format | Raw format exposed to all users | Error prevention | Minor | Hide from default list |
| 15 | Generation progress | Only shows "Generating..." | Visibility | Minor | Show streaming progress |

---

## Gap Analysis Summary

| Server Feature | UI Status | Recommendation |
|----------------|-----------|----------------|
| 16 TTS providers | 4 exposed | **Keep** - Show only enabled providers |
| Voice cloning CRUD | Missing | **Add** - Major feature gap |
| 9 output formats | 6 exposed | **Add ogg/webm** - Hide pcm/ulaw |
| Text normalization | Hidden | **Add** - Single toggle + advanced |
| Speed 0.25-4x | 0.25-2x | **Extend** to 4x |
| Emotion control | Hidden | **Add** - Per-provider when supported |
| Language selection | Implicit | **Keep** - Voice selection adequate |
| WebSocket streaming | Not used | **Keep** - HTTP adequate |
| SSML support | Toggle in settings | **Keep** - Current approach fine |
| Voice design | Hidden | **Keep** - Too advanced |
| Speech-to-Speech API | Unused | **Consider** - For roundtrip mode |

---

## Design Questions - Recommendations

1. **Mode default:** Yes, "Speak" (TTS-only) should be default - most common use case
2. **Provider naming:** Yes, rename "tldw" to "Kokoro (Local)"
3. **Disabled providers:** Hide completely - correct current approach
4. **Voice cloning:** Yes, add dedicated UI section for supported providers
5. **Format selection:** Expose mp3/wav/opus/flac/aac (5) - hide pcm/ulaw
6. **Normalization:** Single "Smart normalization" toggle + expandable advanced
7. **Emotion control:** Surface for relevant providers when selected
8. **History mixing:** Keep combined with filters - current approach is good
9. **Waveform:** Keep - provides good feedback during playback
10. **Settings location:** Split by frequency: common settings in-page, advanced in panel

---

## Priority Recommendations

### High Priority (Before next release)
1. ~~Rename "tldw" provider to "Kokoro (Local)"~~ **DONE** - Updated in `provider-registry.ts`
2. Group settings into Basic/Advanced sections
3. Add character/word count to text input

### Medium Priority (Next sprint)
4. Add "Smart normalization" toggle
5. Extend speed range to 4x
6. Add streaming progress indicator
7. Rename "Roundtrip" to "Speech-to-Speech"

### Low Priority (Backlog)
8. Voice cloning UI (if feature is prioritized)
9. Emotion controls for supported providers
10. Format selection at download time
11. Clip search functionality
12. Side-by-side comparison view

---

## Implementation Notes

### Changes Made (2026-01-27)

1. **Provider Naming Fix**
   - File: `apps/packages/ui/src/utils/provider-registry.ts`
   - Changed `ttsLabel` for "tldw" provider from "tldw server (audio/speech)" to "Kokoro (Local)"
   - This clarifies that the local TTS engine is Kokoro

2. **Settings Descriptions Added**
   - Files:
     - `apps/packages/ui/src/components/Option/Settings/TTSModeSettings.tsx`
     - `apps/tldw-frontend/extension/components/Option/Settings/TTSModeSettings.tsx`
   - Added description text under "Remove Reasoning Tag from TTS" to explain the feature
   - Added description text under "Playback Speed" to clarify it's for playback, not generation

3. **Locale Updates**
   - Files:
     - `apps/packages/ui/src/assets/locale/en/settings.json`
     - `apps/tldw-frontend/extension/assets/locale/en/settings.json`
   - Added `description` keys for `removeReasoningTagTTS` and `playbackSpeed`

---

*Review complete. This document should be used to prioritize UI improvements for the Speech Playground TTS feature.*
