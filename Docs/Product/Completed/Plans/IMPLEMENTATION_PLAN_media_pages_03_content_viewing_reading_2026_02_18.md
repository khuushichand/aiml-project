# Implementation Plan: Media Pages - Content Viewing and Reading

## Scope

Pages/components: media content pane and section tools (`ContentViewer.tsx`, `ViewMediaPage.tsx`, media transcript area)
Finding IDs: `3.1` through `3.11`

## Finding Coverage

- Critical reading continuity and session restore: `3.4`
- High-impact media interaction gap: `3.9`
- Reading comfort and polish improvements: `3.2`, `3.6`, `3.11`
- Preserve strong implemented behavior: `3.1`, `3.3`, `3.5`, `3.7`, `3.8`, `3.10`

## Stage 1: Reading Progress End-to-End
**Goal**: Implement full frontend support for backend reading progress APIs.
**Success Criteria**:
- `useMediaReadingProgress` hook added with GET/PUT/DELETE support.
- Debounced scroll progress is persisted per media item.
- Selecting a media item restores last known position/page/CFI where relevant.
**Tests**:
- Hook unit tests for debounce, merge, and reset behavior.
- Integration tests for save/restore across media switches.
- Regression test verifying no extra writes when content is unchanged.
**Status**: Complete

Progress Notes (2026-02-18):
- Wired `ContentViewer` scroll container to `useMediaReadingProgress` so `/media` now restores and persists reader position for media items.
- Added CFI fallback parsing (`scroll:<percent>`) for restore when `percent_complete` is unavailable.
- Added per-media signature reset and deduped save logic to prevent redundant PUT calls when position is unchanged.
- Added coverage in `src/hooks/__tests__/useMediaReadingProgress.test.tsx`:
  - Restore from `percent_complete`
  - Restore from CFI fallback
  - Debounced save + unchanged-state dedupe
  - Save/restore continuity when switching between media items

## Stage 2: Reading Ergonomics Controls
**Goal**: Improve long-form readability without creating layout instability.
**Success Criteria**:
- Text density/size control (S/M/L) added and persisted per user setting.
- Back-to-top floating action appears after threshold scroll depth and is keyboard accessible.
- Existing content display mode behavior (plain/markdown/html) remains intact.
**Tests**:
- Component tests for text size state and rendering classes.
- Integration tests for back-to-top threshold and action behavior.
- Regression tests for content mode switching and sanitization path.
**Status**: Complete

Progress Notes (2026-02-18):
- Added persisted media text-size setting (`S/M/L`) via `MEDIA_TEXT_SIZE_PRESET_SETTING`.
- Added compact text-size controls to the content toolbar and applied sizing consistently across plain, markdown, and rich-html render modes.
- Added floating `Back to top` action that appears after 500px scroll and supports keyboard/button activation.
- Added test coverage in `src/components/Media/__tests__/ContentViewer.stage2.test.tsx`:
  - Text-size class changes in plain mode
  - Back-to-top visibility threshold + action behavior
  - Markdown mode stability while changing text size

## Stage 3: Embedded Media Playback and Transcript Seeking
**Goal**: Support in-context audio/video review in the content view.
**Success Criteria**:
- Items with original media files show embedded HTML5 audio/video player.
- Transcript timestamps become clickable and seek player position.
- Existing "View original file" action remains available and functional.
**Tests**:
- Component tests for player conditional rendering by media type/file availability.
- Integration tests for timestamp click -> seek behavior.
- Regression tests for original-file action and transcript rendering fallback.
**Status**: Complete

Progress Notes (2026-02-18):
- Added embedded media loading for audio/video items with `has_original_file` using `/api/v1/media/{id}/file` and object-URL playback.
- Added inline HTML5 `<audio>/<video>` player in the content section for playable media types.
- Added transcript timestamp chips (for leading timestamps like `00:12` / `[00:12]`) that seek player position.
- Kept existing actions intact, including the existing original-file action path in viewer menus.
- Added coverage in `src/components/Media/__tests__/ContentViewer.stage3.test.tsx`:
  - Embedded player renders for audio with original file
  - Timestamp click seeks playback time

## Stage 4: Dev-Only Surfaces and Baseline Protection
**Goal**: Restrict developer-only diagnostics and preserve proven reading UX patterns.
**Success Criteria**:
- `DeveloperToolsSection` gated behind feature flag or explicit dev mode.
- Strong current patterns (layout comfort, section navigator, analysis distinction, copy actions) remain unchanged.
- Existing section-resume behavior continues to work per user/media.
**Tests**:
- Feature-flag tests for developer section visibility.
- Regression tests for section navigator traversal and restore behavior.
- Keyboard/accessibility tests for content and analysis section actions.
**Status**: Complete

Progress Notes (2026-02-18):
- Added explicit dev-mode gating for `DeveloperToolsSection` via `shouldShowMediaDeveloperTools()`.
- Added gating test coverage in `src/components/Media/__tests__/ContentViewer.stage4.test.ts`.
- Added section navigator restore-regression coverage for deep-node restoration on post-mount selection changes in `src/components/Media/__tests__/MediaSectionNavigator.test.tsx`.
- Added keyboard/accessibility action coverage for content/analysis section toggles and labeled action buttons in `src/components/Media/__tests__/ContentViewer.stage4.accessibility.test.tsx`.

## Dependencies

- Stage 1 overlaps with Category 14 (`14.2`) and should share the same progress model.
- Stage 3 should align with embedded playback plans in Category 14 (`14.9`).
