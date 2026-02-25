# Workspace Custom Header Banners Design

**Date:** 2026-02-25
**Status:** Approved (revised after risk review)
**Scope:** Research Workspace (`/workspace-playground`) in shared UI, with WebUI and extension parity

## 1. Goal
Add per-workspace custom header banners with:
- local image upload (v1 source: local file only)
- title override
- subtitle override

Banner settings must persist per workspace and survive workspace lifecycle operations:
- switch
- duplicate
- archive/restore
- export/import

## 2. Product Decisions
- Parity policy: WebUI + extension should behave the same unless explicitly extension-only.
- V1 customization scope: image + title + subtitle.
- Image source in v1: local upload only.
- Banner settings are workspace data (not global UI preference).
- Entry point: `WorkspaceHeader` actions menu -> "Customize banner".

## 3. Current-State Risks Found
1. Storage risk: workspace persistence offloads only artifacts/chat payloads; banners would otherwise stay inline and increase quota pressure.
2. Recovery gap: quota recovery currently evicts archived snapshots/chat/oversized artifacts, not future banner payloads.
3. Export/import gap: bundle schema and mappers are explicit and currently exclude banner fields.
4. Conflict visibility gap: cross-tab change banner does not track banner fields.
5. Parity gap: extension route registry currently does not expose `/workspace-playground`.

This design incorporates fixes for all five.

## 4. Revised Architecture
### 4.1 Shared surface
Implement banner model and UI in `apps/packages/ui` so both WebUI and extension use the same code path.

### 4.2 New component
Add `WorkspaceBanner` render block inside `WorkspacePlayground` above `workspace-session-status-strip`.

### 4.3 Edit flow
Add a new `WorkspaceHeader` menu action:
- `customize-banner`

It opens a modal containing:
- title input
- subtitle textarea
- image upload/replace/remove
- live preview
- Save / Cancel / Reset

### 4.4 State ownership
Banner state is part of `WorkspaceSnapshot` and active workspace state in `useWorkspaceStore`.

## 5. Data Model
Add a banner model (names can be adjusted for existing conventions):

```ts
type WorkspaceBannerImage = {
  dataUrl: string
  mimeType: "image/jpeg" | "image/png" | "image/webp"
  width: number
  height: number
  bytes: number
  updatedAt: Date
}

type WorkspaceBanner = {
  title: string
  subtitle: string
  image: WorkspaceBannerImage | null
}
```

Add to snapshot/state:
- `workspaceBanner: WorkspaceBanner`

Validation rules:
- `title`: trimmed, max 80 chars
- `subtitle`: trimmed, max 180 chars
- empty strings allowed

Default:
- `title = ""`, `subtitle = ""`, `image = null`

## 6. Storage and Quota Strategy (Revised)
### 6.1 Upload normalization pipeline (required)
Before persisting:
1. accept only `image/jpeg`, `image/png`, `image/webp`
2. decode image
3. resize to max long edge (target 1400px)
4. encode as `webp` (fallback jpeg if needed)
5. enforce final byte cap (target <= 350 KB serialized payload budget)

If cap is exceeded after normalization:
- reject save with actionable inline error

### 6.2 Persistence behavior
Store normalized banner in workspace snapshot so it naturally follows lifecycle operations.

### 6.3 Recovery behavior updates
Extend quota recovery logic to evict banner images from least-recently-used archived workspaces before deleting larger user content categories.

Add a recovery mutation action type for observability (for example `banner_image_removed`).

### 6.4 Diagnostics visibility
Update persistence metrics sectioning so banner bytes are visible in diagnostics (new `workspaceBanner` section contribution).

## 7. Snapshot Lifecycle Coverage (Required File Touches)
Update all explicit snapshot transformers to include banner:
- `createEmptyWorkspaceSnapshot`
- `applyWorkspaceSnapshot`
- `buildWorkspaceSnapshot`
- `duplicateWorkspaceSnapshot`
- `reviveWorkspaceSnapshot`
- legacy migration builder (`buildLegacyTopLevelSnapshotForMigration` defaulting)

This avoids banner loss on duplicate/new/import/switch.

## 8. Export/Import Coverage
Update bundle schema and mappers:
- `WorkspaceBundleSnapshot` includes `workspaceBanner`
- `buildWorkspaceBundleSnapshot` includes banner
- `hydrateWorkspaceBundleSnapshot` restores banner safely
- export/import round-trip tests cover banner preservation

If imported payload has invalid banner image metadata/data:
- fail soft: clear image only, preserve title/subtitle

## 9. Cross-Tab Conflict Coverage
Add `workspaceBanner` to:
- `WORKSPACE_CONFLICT_TRACKED_FIELDS`
- label mapping for conflict message text

This makes concurrent banner edits visible in existing "Use latest / Keep mine / Fork copy" flow.

## 10. WebUI/Extension Parity Plan
### 10.1 Route parity precondition
Add `/workspace-playground` route exposure in extension route registry (shared UI route component) so this feature is accessible and testable in extension.

### 10.2 Shortcut parity
Ensure header/sidebar shortcuts that target `/workspace-playground` do not point to non-registered routes in extension mode.

### 10.3 Behavior parity
No platform-specific banner logic. Any divergence must be explicitly documented as extension-only constraint.

## 11. UX and Accessibility Requirements
- Keep fallback/default workspace header look when no banner configured.
- Apply overlay gradient for text readability on image banners.
- Keyboard-accessible modal and controls.
- `aria-label` on all icon-only controls.
- Mobile: reduced banner height, line-clamp title/subtitle.
- Preserve existing guardrail banners and skip-links ordering.

## 12. Error Handling
Inline errors in modal for:
- unsupported file type
- upload too large
- processing/encoding failure
- persistence failure (quota/storage)

Behavior:
- Cancel leaves current banner unchanged.
- Reset clears current workspace banner config immediately after confirm.
- Corrupt persisted image payload is dropped on hydrate; text fields remain.

## 13. Testing Strategy
### 13.1 Store unit tests
- snapshot defaults include banner
- set/update/clear banner updates active state and snapshot
- switch/duplicate/archive/restore preserve banner
- quota recovery can evict banner payloads predictably

### 13.2 Bundle tests
- export/import round-trip preserves banner
- invalid imported banner payload fails soft (image cleared, text retained)

### 13.3 Component tests
- `WorkspaceHeader` menu exposes customize action
- modal validation and save behavior
- banner render with/without image
- reset/remove flows
- mobile clamp and a11y labels

### 13.4 Parity tests
- WebUI route renders banner
- extension route renders same behavior for `/workspace-playground`

## 14. Rollout and Safety
- Keep behind existing route; no global flags required for v1.
- Consider optional kill switch if storage regressions appear in telemetry.
- Post-release checks:
  - quota warning incidence
  - recovery action counts
  - workspace import/export failure rates

## 15. Non-Goals (v1)
- media-library image selection
- server-hosted banner assets
- multi-banner templates
- advanced visual effects (parallax/filters/animations)

## 16. Open Follow-Ups (Post-v1)
- optional IndexedDB pointer offload for banner images (same pattern as artifacts/chat) if quota pressure remains high
- media-library picker as alternative image source
- richer typography/theming controls
