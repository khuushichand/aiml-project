# Reading List Digest Suggestions (Design)

## Summary
Add an optional "suggestions" section to Reading List digests. Suggestions are a curated subset of reading items not already in the digest, ranked by simple heuristics (recency, favorites, tag overlap, status). The goal is to help users discover items worth reading without introducing heavy personalization or external dependencies.

This is a stretch goal that builds on the existing digest scheduler and output templates. Suggestions are opt-in per schedule and remain local only.

## Goals
- Provide a configurable suggestions list in digest outputs.
- Keep suggestions local-only, deterministic, and explainable.
- Use lightweight heuristics and existing data; avoid new external services.
- Keep the digest template API stable while adding new optional context fields.

## Non-Goals
- Cross-user or cross-device personalization.
- External recommendation services or ML training pipelines.
- Real-time recommendation updates outside of scheduled digests.

## User Stories
- As a user, I can enable "suggested reads" in my daily digest.
- As a user, I can control how many suggestions I get and which statuses they come from.
- As a user, I can see why an item was suggested (optional, brief reason).

## Proposed Behavior

### 1) Selection Flow
When a digest schedule runs:
1. Generate the primary digest items using the existing filters.
2. If suggestions are enabled, compute a suggestion pool:
   - Exclude any items already in the digest.
   - Default to status in {"saved", "reading"}.
   - Exclude archived or read items unless explicitly allowed.
3. Score and rank candidates using a lightweight heuristic.
4. Select top N suggestions and attach to the template context and metadata.

### 2) Heuristic Scoring (Initial)
Each candidate gets a score based on:
- Recency: newer items score higher.
- Favorite: favorite items get a small boost.
- Tag overlap: overlap between candidate tags and digest filters boosts score.
- Status: "reading" or "saved" items score higher than "read".
- Reading time: optionally downrank very long items.

This stays deterministic and cheap. The scoring function should be a small pure function for tests.

### 3) Template Context
The digest template gets a new optional field:
- `suggestions`: array of suggestion items with the same shape as `items`.
- `suggestions_meta`: optional info, such as reasons or score (hidden by default).

Templates can ignore suggestions without breaking.

### 4) Output Metadata
Store suggestion info in output artifact metadata:
- `suggestions_count`
- `suggestions_item_ids`
- `suggestions_config` (sanitized schedule config)

## Data Model

### Schedule Config
Extend `filters_json` to include an optional `suggestions` block:
```json
{
  "status": ["saved"],
  "tags": ["ai"],
  "limit": 10,
  "suggestions": {
    "enabled": true,
    "limit": 5,
    "status": ["saved", "reading"],
    "exclude_tags": ["ignore"],
    "max_age_days": 90,
    "include_read": false,
    "include_archived": false
  }
}
```

This avoids a schema migration and keeps backward compatibility.

### API
Update `ReadingDigestScheduleFilters` to allow the optional `suggestions` field.
No new endpoints needed.

## UI/UX (Next.js WebUI)
- In the digest schedule editor: add a "Suggestions" toggle.
- Show fields when enabled: limit, status list, optional exclude tags.
- Provide a short hint that suggestions are local-only and heuristic-based.

## Implementation Notes
- Add a helper in the reading digest job to compute suggestions.
- Use existing `ReadingService.list_items` for candidate retrieval.
- Filter and score in-memory; keep a reasonable upper bound (e.g., max 200 candidates).
- Exclude items already in the digest by item id.

## Metrics
- Number of digests with suggestions enabled.
- Suggestions count per digest.
- (Optional) Exported reason counts by heuristic category.

## Tests
- Unit tests for suggestion scoring and filtering.
- Integration test to verify suggestions appear in output metadata and template context.
- Ensure disabled suggestions do not alter outputs.

## Rollout
- Phase 1: backend computation + template context + metadata.
- Phase 2: UI toggle in schedule editor.
- Phase 3: refine scoring weights based on feedback.

## Open Questions
- Should suggestions default to enabled for new schedules, or off?
- Should we expose "reasons" in the template context by default?
- Do we want an optional embeddings-based similarity pass in the future?
