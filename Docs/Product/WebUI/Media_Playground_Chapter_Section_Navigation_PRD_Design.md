# Media Playground Chapter/Section Navigation + Optional Rich Rendering (Combined PRD + Design)

Status: Review Ready
Owner: Core Maintainers (WebUI + Media API)
Audience: Product, Frontend, Backend, QA
Last Updated: 2026-02-09

---

## 1. Executive Summary

### Problem
Media Playground currently exposes content mostly as a single long body. Users cannot reliably jump to a specific chapter/section (for example, Chapter 12, Section 5), which slows review workflows for long media items (books, transcripts, long-form documents).

### Proposed Solution
Add a section-aware navigation experience to Media Playground with:
1. A left-side Chapter/Section navigator.
2. Quick jump by section number or title.
3. Section-targeted display in the content pane.
4. Optional render mode switch (`Auto`, `Plain`, `Markdown`, `Rich`) for content display.

### Outcome
Users can open a media item, select a chapter/section, and immediately view targeted content in the preferred rendering mode for faster navigation and review.

---

## 2. Goals

1. Enable fast navigation to chapter/section targets for supported media types.
2. Normalize navigation data into a single client contract across document/text/audio/video items.
3. Provide optional rendering modes (plain, markdown, rich) with safe defaults.
4. Reuse existing platform components and endpoint patterns where possible.

## 3. Non-Goals

1. Replacing Document Workspace as the primary PDF/EPUB reader.
2. Building a WYSIWYG editor for media content.
3. Guaranteeing perfect chapter extraction for all legacy ingested items.
4. Blocking release on LLM-generated segmentation quality improvements.

---

## 4. Users and Jobs-to-be-Done

1. Research user reviewing long reports: jump directly to target section and skim quickly.
2. Transcript reviewer: navigate by topic/time ranges rather than scrolling full transcript.
3. Knowledge worker revisiting prior ingest: reopen last section and continue from prior location.

Primary JTBD: "When I open a long media item, I want it pre-split into chapters/sections so I can quickly navigate to the exact part I need and read it in the format I prefer."

---

## 5. Current Baseline (Codebase)

### Frontend
1. Media Playground route and page:
   - `apps/packages/ui/src/routes/option-media.tsx`
   - `apps/packages/ui/src/components/Review/ViewMediaPage.tsx`
2. Content rendering container:
   - `apps/packages/ui/src/components/Media/ContentViewer.tsx`
3. Current markdown renderer utility:
   - `apps/packages/ui/src/components/Common/MarkdownPreview.tsx`
4. Existing setting for collapsed sections:
   - `apps/packages/ui/src/services/settings/ui-settings.ts` (`MEDIA_COLLAPSED_SECTIONS_SETTING`)

### Backend
1. Media details endpoint:
   - `GET /api/v1/media/{media_id}`
   - `tldw_Server_API/app/api/v1/endpoints/media/item.py`
2. PDF outline endpoint already exists:
   - `GET /api/v1/media/{media_id}/outline`
   - `tldw_Server_API/app/api/v1/endpoints/media/document_outline.py`
3. Transcript segmentation endpoint already exists:
   - `POST /api/v1/audio/segment/transcript`
4. Structural metadata exists in DB layer:
   - `DocumentStructureIndex`
   - chunk metadata fields such as `section_path` and `ancestry_titles` in chunk persistence flow.

---

## 6. Product Requirements

### 6.1 Functional Requirements

1. FR-1: Section Navigator
   - Media view MUST show a chapter/section navigation panel when structure data is available.

2. FR-2: Quick Jump
   - Users MUST be able to jump via numeric tokens (`12`, `12.5`) and title search.

3. FR-3: Deterministic Section Selection Behavior
   - Selecting a section node MUST use behavior defined by its `target_type`:
     - `char_range`: client MUST fetch `GET /api/v1/media/{media_id}/navigation/{node_id}/content` and render the returned section payload.
     - `page`: client MUST navigate to the target page in document-capable view; if page navigation is unavailable, client MUST fallback to section payload rendering.
     - `time_range`: client MUST seek media/transcript view to `target_start`; if section payload is available, client SHOULD also render it in the content pane.
     - `href`: client MUST navigate only to internal document anchors; external href targets MUST be rejected.

4. FR-4: Render Modes (Canonical Mapping)
   - Media view MUST expose UI labels:
     - `Auto`
     - `Plain`
     - `Markdown`
     - `Rich`
   - Canonical API values MUST be:
     - `auto`
     - `plain`
     - `markdown`
     - `html`
   - Mapping MUST be fixed as:
     - `Auto` -> `auto`
     - `Plain` -> `plain`
     - `Markdown` -> `markdown`
     - `Rich` -> `html`

5. FR-5: Auto Mode Behavior
   - `Auto` MUST prefer the best available format in this priority:
     - `html` (Rich)
     - `markdown`
     - `plain`

6. FR-6: Persistence and Resume
   - System SHOULD persist last selected `node_id`, `navigation_version`, and render mode per user and server context.
   - Persisted resume state MUST be namespaced by `(server_fingerprint, user_id, media_id)` to prevent cross-user or cross-server collisions.
   - Persisted resume state MUST be bounded by policy:
     - max 1000 media resume entries per `(server_fingerprint, user_id)` scope.
     - eviction strategy: LRU based on `last_accessed_at`.
     - optional cleanup: remove entries not accessed for 90 days.
   - Render mode precedence MUST be:
     1. per-media override (if enabled in future phase),
     2. scoped global preference `(server_fingerprint, user_id)`,
     3. default `auto`.
   - MVP decision: use scoped global preference only; per-media override is deferred.
   - On stale/unknown `node_id`, client MUST refetch navigation and recover selection in this order:
     1. exact `path_label` match
     2. case-insensitive title match at same or nearest depth
     3. first root node

7. FR-7: Fallback Behavior
   - If no structure data exists, UI MUST degrade gracefully to current full-content behavior.

### 6.2 Non-Functional Requirements

1. NFR-1: Initial navigation load p95 < 400 ms under baseline payload assumptions:
   - dataset size up to 500 nodes.
   - average title length <= 80 chars.
   - compressed response size <= 200 KB.
2. NFR-2: Section switch response p95 < 250 ms when content is already loaded/cached and delivered payload <= 64 KB compressed.
3. NFR-3: Rich HTML rendering MUST use a centralized allowlist sanitizer policy before DOM injection.
4. NFR-4: Feature must preserve keyboard accessibility for navigation and quick jump.
5. NFR-5: API payload guardrails MUST be explicit and enforced:
   - navigation defaults: `max_depth=4`, `max_nodes=500`.
   - content endpoint default: single-format payload only (no alternates unless explicitly requested).
6. NFR-6: All performance SLO checks MUST be reported with fixture size, cache state (cold/warm), and whether payload truncation occurred.
7. NFR-7: Client persistence storage MUST remain bounded and auditable:
   - per-scope resume entries capped at 1000.
   - eviction and restore paths emit telemetry for debugging.
8. NFR-8: Security policy for rich rendering MUST enforce:
   - disallowed tags: `script`, `style`, `iframe`, `object`, `embed`, `link`, `meta`, `base`, `form`, `input`, `button`, `textarea`, `select`.
   - disallowed attributes: all `on*` event handlers and inline CSS style attributes.
   - allowed URL protocols for `href/src`: `http`, `https`, `mailto`, `tel`, and same-document anchors.
   - blocked URL schemes: `javascript:`, `data:`, `vbscript:`, `file:`.
9. NFR-9: No bypass path is allowed:
   - rich HTML rendering MUST only use centralized sanitizer config.
   - direct unsanitized `dangerouslySetInnerHTML` usage for this feature is prohibited.

---

## 7. UX Specification

### 7.1 Layout

Three-region layout in media detail view:
1. Left: `Chapters/Sections` tree and quick jump.
2. Center: content area with display-mode selector.
3. Existing metadata/analysis blocks remain intact (or collapsed) below/adjacent depending on current layout mode.

### 7.2 User Flow

1. User selects media item from list.
2. Client requests navigation tree.
3. Tree renders with hierarchical nodes.
4. User selects `Chapter 12 > Section 5`.
5. Client fetches/derives section content target.
6. Content renders in selected mode (`Auto/Plain/Markdown/Rich`).

### 7.3 Interaction Details

1. Section node click:
   - updates active breadcrumb.
   - executes FR-3 target-type behavior deterministically.
2. Quick Jump:
   - type-ahead support for title and number tokens.
   - `Enter` selects top match.
3. Display mode selector:
   - segmented control in content header.
   - changing mode re-renders same selected section only.

---

## 8. Data Contract and API Design

### 8.0 Canonical Enums and Stability Scope

1. Canonical content format enum for API requests/responses:
   - `auto | plain | markdown | html`
2. UI label mapping (must remain stable):
   - `Auto -> auto`, `Plain -> plain`, `Markdown -> markdown`, `Rich -> html`
3. `node_id` stability scope:
   - guaranteed stable only within a `(media_id, navigation_version)` pair.
   - not guaranteed stable across reprocess/version/source-priority changes.
4. Resume scope keying:
   - all persisted client resume data is scoped by `(server_fingerprint, user_id)`.
   - media-specific resume adds `media_id` within that scope.

### 8.1 Navigation Node Contract

```json
{
  "id": "sec_12_5",
  "parent_id": "sec_12",
  "level": 2,
  "title": "Section 5: Error Analysis",
  "order": 5,
  "path_label": "12.5",
  "target_type": "char_range",
  "target_start": 45210,
  "target_end": 49780,
  "target_href": null,
  "source": "document_structure_index",
  "confidence": 0.95
}
```

Fields:
1. `id`: stable node id within current `navigation_version`.
2. `parent_id`: null for roots.
3. `level`: display depth.
4. `title`: user-visible heading.
5. `order`: sibling order.
6. `path_label`: optional numeric path for quick jump (`12.5`).
7. `target_type`: `page | char_range | time_range | href`.
8. `target_start` / `target_end`: coordinates with type-specific semantics (see 8.1.1).
9. `target_href`: required when `target_type=href`, otherwise null.
10. `source`: provenance (`pdf_outline`, `document_structure_index`, `transcript_segment`, `generated`).
11. `confidence`: extraction confidence.

### 8.1.1 Target Coordinate Semantics (Normative)

1. `char_range`
   - `target_start` and `target_end` are integer character offsets in canonical stored text.
   - 0-indexed; `target_start` inclusive, `target_end` exclusive.
   - MUST satisfy `0 <= target_start < target_end`.
2. `page`
   - `target_start` is a 1-indexed page number.
   - `target_end` MUST be null.
3. `time_range`
   - `target_start` and `target_end` are seconds from media start (float allowed).
   - `target_start` inclusive, `target_end` exclusive when present.
   - `target_end` MAY be null for point seek.
4. `href`
   - `target_href` contains an internal document anchor reference.
   - `target_start` and `target_end` MUST be null.

### 8.2 New Endpoints

1. `GET /api/v1/media/{media_id}/navigation`
   - Returns normalized tree for media item.
   - Query flags:
     - `include_generated_fallback` (default `false`)
     - `max_depth` (default `4`, max `8`)
     - `max_nodes` (default `500`, max `2000`)
     - `parent_id` (optional; when provided, return only direct children for lazy tree expansion)
   - Response behavior:
     - if node count exceeds `max_nodes`, server MUST return a truncated result with `stats.truncated=true`.

2. `GET /api/v1/media/{media_id}/navigation/{node_id}/content`
   - Returns content payload for selected node.
   - Query params:
     - `format=auto|plain|markdown|html`
     - `include_alternates=true|false` (default `false`)
   - Response behavior:
     - default response MUST include only one content body (`content`) corresponding to resolved `content_format`.
     - if `include_alternates=true`, server MAY include `alternate_content` map for other available formats.
   - Error behavior:
     - if `node_id` is not present in current navigation set, return `404` with `error_code="NAVIGATION_NODE_NOT_FOUND"` and current `navigation_version`.

### 8.3 Response Shape: Navigation

```json
{
  "media_id": 123,
  "available": true,
  "navigation_version": "media_123:v7:9f3c0f5d",
  "source_order_used": [
    "pdf_outline",
    "document_structure_index",
    "transcript_segment"
  ],
  "nodes": [],
  "stats": {
    "returned_node_count": 84,
    "node_count": 84,
    "max_depth": 4,
    "truncated": false
  }
}
```

Navigation response notes:
1. `navigation_version` MUST change when structural data changes (reprocess/version/source-priority differences).
2. Clients MUST treat persisted `node_id` values without matching `navigation_version` as stale.
3. `node_count` is total available nodes before truncation; `returned_node_count` is actual nodes returned.
4. When `stats.truncated=true`, client SHOULD request a narrower tree (for example lower depth or lazy children via `parent_id`).

### 8.4 Response Shape: Section Content

```json
{
  "media_id": 123,
  "node_id": "sec_12_5",
  "title": "Section 5: Error Analysis",
  "content_format": "markdown",
  "available_formats": ["plain", "markdown"],
  "content": "### Section 5...",
  "alternate_content": null,
  "target": {
    "target_type": "char_range",
    "target_start": 45210,
    "target_end": 49780
  }
}
```

Section content response notes:
1. Default response (`include_alternates=false`) MUST include only:
   - `content_format`
   - `content`
2. If `include_alternates=true`, `alternate_content` MAY include a sparse map, for example:
   - `{ "plain": "...", "html": "<p>...</p>" }` excluding the selected `content_format`.
3. `format=auto` MUST resolve to one concrete `content_format` in response.

---

## 9. Backend Technical Design

### 9.1 Source Priority for Navigation Extraction

1. PDF/EPUB outline data (existing outline paths).
2. `DocumentStructureIndex` hierarchy.
3. Chunk metadata (`section_path`, `ancestry_titles`).
4. Transcript segments (timestamp-based for audio/video).
5. Optional generated fallback segmentation (low confidence, explicit provenance).

### 9.2 Implementation Locations

1. Endpoint module (new):
   - `tldw_Server_API/app/api/v1/endpoints/media/navigation.py`
2. Schema additions:
   - `tldw_Server_API/app/api/v1/schemas/media_response_models.py`
3. DB/helper composition:
   - `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

### 9.3 Persistence and Caching

1. Cache navigation payload by media/version hash.
2. Invalidate on media update/reprocess/version mutation.
3. Cache section content slices for frequent revisit.

### 9.4 Security

1. Maintain existing media auth and RBAC dependencies.
2. Do not include secrets or internal paths in payloads.
3. Keep generated fallback opt-in (avoid hidden model execution in baseline path).
4. Define and enforce one centralized sanitizer policy for Rich mode.
5. Sanitizer policy (normative):
   - allow safe structural/content tags only (for example `p`, `div`, `span`, `h1-h6`, `ul`, `ol`, `li`, `blockquote`, `code`, `pre`, `strong`, `em`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `a`, `img`).
   - strip disallowed tags listed in NFR-8.
   - strip all event-handler attributes (`on*`) and inline style attributes.
   - only allow URL protocols listed in NFR-8.
   - force external links to safe behavior (`rel="noopener noreferrer nofollow"`).
6. `href` target-type navigation MUST allow only internal anchors for document navigation and reject external targets.
7. When sanitization removes unsafe content, UI SHOULD render sanitized remainder and emit a security telemetry event.

---

## 10. Frontend Technical Design

### 10.1 Reuse Strategy

1. Reuse TOC/tree patterns from Document Workspace:
   - `apps/packages/ui/src/components/DocumentWorkspace/LeftSidebar/TableOfContentsTab.tsx`
2. Reuse markdown rendering and boundary:
   - `apps/packages/ui/src/components/Common/MarkdownPreview.tsx`
   - `apps/packages/ui/src/components/Common/MarkdownErrorBoundary.tsx`
3. Reuse HTML sanitization pattern (`DOMPurify`) where rich rendering is enabled.
4. Introduce a single shared sanitizer utility/config for Media Playground rich rendering (no per-component sanitizer drift).

### 10.2 New UI State

Add local setting(s):
1. `tldw:media:contentDisplayModeByScope`
   - map key: `{server_fingerprint}:{user_id}`
   - value: `auto|plain|markdown|html`
2. `tldw:media:navigationResumeIndex`
   - map key: `{server_fingerprint}:{user_id}:{media_id}`
   - value:
     - `node_id`
     - `navigation_version`
     - `path_label` (optional)
     - `last_accessed_at`
3. Bounded retention policy:
   - max 1000 `navigationResumeIndex` entries per `{server_fingerprint}:{user_id}` scope.
   - evict least-recently-used entries first.
4. MVP precedence:
   - use scoped global display mode only.
   - do not persist per-media mode override in MVP.

### 10.3 Content Rendering Rules

1. `Plain`
   - render as escaped text with whitespace preservation.
2. `Markdown`
   - render with `MarkdownPreview`.
3. `Rich`
   - render sanitized HTML only via centralized policy.
   - if sanitized output is empty, fallback to safe plain-text rendering for that section.
4. `Auto`
   - prefer html > markdown > plain based on available formats.

### 10.4 UI Components (proposed)

1. `MediaSectionNavigator.tsx`
2. `MediaContentDisplayModeToggle.tsx`
3. `useMediaNavigation.ts`
4. `useMediaSectionContent.ts`

Integration targets:
1. `apps/packages/ui/src/components/Review/ViewMediaPage.tsx`
2. `apps/packages/ui/src/components/Media/ContentViewer.tsx`

---

## 11. Observability and Metrics

1. `media_navigation_loaded` with node count and source type.
2. `media_navigation_section_selected` with depth and latency.
3. `media_content_display_mode_changed` with mode and media type.
4. `media_navigation_fallback_used` for no-structure or generated path usage.
5. `media_navigation_payload_truncated` with requested/returned node counts.
6. `media_navigation_content_payload_size` with format, compressed bytes, and whether alternates were included.
7. `media_navigation_resume_state_restored` with restore outcome (`exact`, `path_label`, `title_depth`, `root_fallback`).
8. `media_navigation_resume_state_evicted` with scope key hash and evicted entry count.
9. `media_rich_sanitization_applied` with removed-node and removed-attribute counts.
10. `media_rich_sanitization_blocked_url` with blocked scheme type.

Success metrics:
1. Reduced median time-to-target-section.
2. Increased repeated section navigation events per session.
3. Increased usage of non-default display modes when markdown/html are available.

---

## 12. Testing Plan

### 12.1 Backend

1. Unit tests:
   - source-priority selection logic.
   - node normalization and path labels.
   - section slicing bounds.
2. Integration tests:
   - `GET /navigation` for document and transcript-backed items.
   - `GET /navigation` guardrails (`max_depth`, `max_nodes`, `parent_id`) and `stats.truncated` behavior.
   - `GET /navigation/{node_id}/content` with each `format` option.
   - `GET /navigation/{node_id}/content` default single-format payload vs `include_alternates=true`.
   - auth and not-found behaviors.
   - `href` target validation rejects external targets for internal navigation behavior.
3. Performance tests:
   - fixture-backed p50/p95 checks for baseline dataset (<= 500 nodes, <= 200 KB compressed navigation payload).
   - section-switch latency checks for cached and uncached paths with payload size capture.

### 12.2 Frontend

1. Unit tests:
   - render mode switch behavior.
   - quick jump matching and selection.
   - display mode precedence behavior (scoped global in MVP).
2. Component tests:
   - chapter tree rendering and selection state.
   - markdown and rich rendering fallback behavior.
   - truncated navigation handling and lazy child-load interaction.
   - scoped resume restore and fallback order behavior.
   - rich sanitizer strips: `<script>`, `<iframe>`, `onerror`, `onclick`, and inline `style`.
   - rich sanitizer blocks URL schemes: `javascript:`, `data:`, `vbscript:`, `file:`.
   - rich sanitizer preserves safe tags and safe links.
3. E2E:
   - select media -> jump section -> toggle render mode -> persist and reopen.
   - content fetch with `include_alternates=false` then opt-in alternates path.
   - same `media_id` across different users/servers restores distinct resume state.
   - malicious HTML sample renders safely without script execution and with blocked links sanitized.

---

## 13. Rollout Plan

### Phase 1 (MVP)
1. Support navigation for documents where outline/structure data exists.
2. Enable display mode toggle for selected/full content.
3. Persist display mode by `(server_fingerprint, user_id)` scope.

### Phase 2
1. Add transcript-derived navigation for audio/video.
2. Add per-media last-node resume with bounded LRU storage.

### Phase 3
1. Optional generated fallback segmentation behind feature flag.
2. Additional ranking/refinement for noisy structure data.

Rollback:
1. Feature flag to disable navigation panel.
2. Fallback to existing full-content render path.

---

## 14. Risks and Mitigations

1. Risk: Inconsistent section quality across media types.
   - Mitigation: source provenance + confidence + graceful fallback.

2. Risk: Rich rendering XSS exposure.
   - Mitigation: strict sanitization and disallow unsafe tags/attrs.

3. Risk: UI complexity in already dense media page.
   - Mitigation: collapsible navigator and conservative default layout.

4. Risk: Performance regressions with large trees.
   - Mitigation: lazy tree rendering and payload caching.

---

## 15. Acceptance Criteria

1. A user can select a media item and see a chapter/section tree when structure exists.
2. A user can jump to a section by number/title and open it in one action.
3. A user can switch among `Auto`, `Plain`, `Markdown`, and `Rich` (API values `auto|plain|markdown|html`) without losing section selection.
4. HTML rendering is sanitized.
5. If no structure exists, user still gets current full-content experience without errors.
6. Section selection behavior is deterministic by `target_type` (`char_range`, `page`, `time_range`, `href`) per FR-3.
7. Resume logic handles stale node IDs by `path_label`, then title/depth, then root-node fallback.
8. `GET /navigation/{node_id}/content` returns single-format content by default and only returns alternates when `include_alternates=true`.
9. `GET /navigation` applies default guardrails (`max_depth=4`, `max_nodes=500`) and signals truncation explicitly.
10. Resume state is isolated by `(server_fingerprint, user_id, media_id)` and does not bleed across users or servers.
11. Resume entry storage remains bounded with LRU eviction at 1000 entries per user/server scope.
12. Display mode precedence follows MVP rule: scoped global preference only (per-media override deferred).
13. Rich mode sanitization removes disallowed tags/attributes and blocks disallowed URL schemes per NFR-8.
14. Rich content rendering paths use centralized sanitizer policy with no bypass usage.
15. Security regression suite (unit/component/E2E malicious payload scenarios) passes.

---

## 16. Resolved Decisions and Feature Flags

1. Analysis block display-mode selector in MVP:
   - Decision: Not included in MVP.
   - Feature flag: `media_playground_analysis_display_mode_selector` (default `false`).
   - Rollout note: revisit in Phase 2 after core content selector adoption metrics.

2. Generated fallback segmentation default behavior:
   - Decision: Enabled by default in the current WebUI rollout.
   - API contract remains explicit via query parameter: `include_generated_fallback=true|false`.
   - Feature flag: `media_navigation_generated_fallback_default` (default `true`).
   - Provenance requirement: generated nodes MUST set `source=generated` and include confidence.

---

## 17. Proposed Initial Implementation Task List

1. Add new media navigation endpoint + schemas.
2. Add frontend hooks for tree and section-content fetch.
3. Add section navigator UI and quick-jump control in Media View.
4. Add content display-mode toggle and sanitized rich renderer.
5. Add unit/integration tests and feature flag wiring.

---

## 18. Issue Traceability Matrix

| Issue | Summary | PRD Sections Updated | Test Coverage Sections | Status |
| --- | --- | --- | --- | --- |
| Issue 1 | Node identity + resume stability ambiguity | 6.1 (FR-6), 8.0, 8.3, 10.2, 15 (AC 7,10,11) | 12.2 (unit/component/E2E resume restore cases) | Closed |
| Issue 2 | Target coordinate semantics ambiguity | 6.1 (FR-3), 8.1, 8.1.1, 15 (AC 6) | 12.1 (section slicing bounds), 12.2 (selection behavior) | Closed |
| Issue 3 | Render enum vocabulary mismatch | 6.1 (FR-4, FR-5), 8.0, 8.2, 10.2, 15 (AC 3) | 12.1 (`format` integration), 12.2 (mode switch unit tests) | Closed |
| Issue 4 | Content endpoint over-fetching risk | 6.2 (NFR-5), 8.2, 8.4, 15 (AC 8) | 12.1 (`include_alternates` integration tests), 12.2 E2E alternates path | Closed |
| Issue 5 | Persistence namespacing + unbounded growth risk | 6.1 (FR-6), 6.2 (NFR-7), 8.0, 10.2, 15 (AC 10,11,12) | 12.2 (cross-user/server isolation + eviction tests) | Closed |
| Issue 6 | FR-3 behavior ambiguity | 6.1 (FR-3), 7.3, 15 (AC 6) | 12.2 component/E2E selection behavior checks | Closed |
| Issue 7 | Performance goals lacked payload assumptions | 6.2 (NFR-1,2,5,6), 8.2, 8.3, 11, 15 (AC 9) | 12.1 performance tests with fixture and cache-state reporting | Closed |
| Issue 8 | Security requirement too generic | 6.2 (NFR-3,8,9), 9.4, 10.1, 10.3, 11, 15 (AC 13,14,15) | 12.1/12.2 malicious payload and blocked-scheme tests | Closed |
| Issue 9 | Test plan gaps | 12.1, 12.2, 15 (AC 15) | 12.1 and 12.2 expanded unit/integration/component/E2E matrix | Closed |

---

## 19. Final Review Signoff Checklist

- [x] Render-mode contract is canonical and consistent across FE/BE.
- [x] Target-type coordinate semantics are explicit and testable.
- [x] Section selection behavior is deterministic by `target_type`.
- [x] Resume state is namespaced, bounded, and has defined fallback behavior.
- [x] API payload guardrails and truncation semantics are explicit.
- [x] Rich rendering security policy is centralized and normative.
- [x] Security regression vectors are defined across unit/component/E2E.
- [x] Acceptance criteria explicitly cover all previously identified risks.
- [x] Internal PRD review found no remaining P1/P2 ambiguity findings in this revision.
