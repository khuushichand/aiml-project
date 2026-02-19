# Chat Dictionary Sharing and Composition Roadmap (2026-02-18)

## Purpose

Define a staged delivery path for dictionary sharing/community workflows while keeping composition (`included_dictionary_ids`) safe, auditable, and compatible with existing AuthNZ/RBAC patterns.

## Scope

- In scope:
  - Share model and access controls for dictionary artifacts.
  - Trust boundaries for imported/shared dictionaries.
  - Composition constraints for included dictionaries across ownership boundaries.
  - Rollout sequencing and feature-flag plan.
- Out of scope:
  - Full UI pixel design.
  - Social discovery/ranking algorithms.
  - Non-dictionary asset sharing (characters, prompts, notes).

## Data Model (Proposed)

- `chat_dictionary_shares`
  - `id`, `dictionary_id`, `owner_user_id`, `visibility` (`private|link|team|public`)
  - `access_policy` JSON (allowed users/roles/scopes)
  - `share_slug` (optional stable URL id), `share_token_hash` (link mode)
  - `created_at`, `updated_at`, `revoked_at`, `expires_at`
- `chat_dictionary_share_audit`
  - immutable audit rows for create/update/revoke/import-from-share actions
  - actor identity, source IP/session, old/new policy snapshot
- Reuse existing `chat_dictionaries.version` + `dictionary_version_history` for snapshot/revert.

## Trust Boundaries

1. Ownership boundary
   - Only owner (or admin with explicit scope) can modify dictionary or its share policy.
   - Imported copies are owned by importer; never grant implicit write-back to source.
2. Execution boundary
   - Shared dictionaries remain data, not code.
   - Regex patterns are revalidated on import/enable using server-side safety checks (including ReDoS guardrails).
3. Composition boundary
   - `included_dictionary_ids` must reference dictionaries readable by the current user/session.
   - Cross-owner includes require explicit grant and are resolved as read-only.
   - Cycle detection is mandatory across the full resolved include graph.
4. Exposure boundary
   - `public` shares expose only approved metadata/entry payload (no private usage analytics by default).
   - Activity/audit endpoints are owner/admin only unless explicitly broadened.
5. Revocation boundary
   - Revoked/expired shares immediately block new access.
   - Existing imported copies remain local unless user opts into sync mode (future phase).

## Authorization Model

- Auth mode compatibility:
  - `single_user`: sharing endpoints disabled by default (feature flag) unless explicitly enabled for local link export.
  - `multi_user`: enforce JWT identity + RBAC checks.
- Suggested scopes:
  - `dictionaries:read`, `dictionaries:write`, `dictionaries:share`, `dictionaries:admin`
- Role mapping:
  - Owner: full control, policy edits, revoke, transfer.
  - Editor (future): can modify dictionary content, cannot change owner.
  - Viewer: read/export/import copy only.

## API Roadmap

### Phase A (MVP, private/link sharing)

- `POST /api/v1/chat/dictionaries/{id}/share` create/update share policy.
- `GET /api/v1/chat/dictionaries/{id}/share` owner view of policy.
- `POST /api/v1/chat/dictionaries/shared/{slug}/import` import as local copy.
- Link-share access controlled by token + optional expiry.

### Phase B (team/gallery)

- `GET /api/v1/chat/dictionaries/shared` list visible team dictionaries.
- Add filters: tags, category, owner, updated_at.
- Add provenance fields on import (`imported_from_share_id`, `imported_from_revision`).

### Phase C (public community)

- Moderated public listing and report workflow.
- Quarantine path for flagged dictionaries.
- Optional reputation/verification metadata for publishers.

## Composition Rules (Operational)

- Include resolution order: DFS, included dictionaries before including dictionary.
- Include eligibility:
  - Same owner: allowed.
  - Different owner: allowed only when reader has read access to included dictionary share.
- On permission loss to included dictionary:
  - Processing skips inaccessible include and returns warning metadata.
  - Save/update operations fail fast with actionable conflict message.

## Composition Precedence (Technical Contract)

- Targeted processing (`dictionary_id` provided):
  - Resolve full include graph from the target dictionary.
  - Execute included dictionaries first, then the target dictionary.
- Global processing (`dictionary_id` omitted):
  - Resolve active dictionaries in deterministic root order (`LOWER(name)`, `id`).
  - For each root, execute DFS includes before root dictionary.
  - Already-visited dictionaries are not reprocessed.
- Conflict handling:
  - Include cycles are rejected at update time and guarded during runtime traversal.
  - Missing/inaccessible include references are validation failures for write operations.

## Version History Retention Policy

- Current implementation behavior:
  - `dictionary_version_history` stores immutable snapshots for key lifecycle mutations.
  - History is retained indefinitely unless dictionary hard-delete cascades rows.
- Recommended operational policy (post-MVP):
  - Keep latest 100 revisions per dictionary permanently.
  - Keep all revisions from last 180 days.
  - Nightly prune revisions older than 180 days that are outside latest 100.
  - Preserve audit metadata for prune actions.
- Compatibility requirement:
  - Revert API must continue to reject missing revisions with explicit `404`.
  - Retention pruning must never remove the most recent revision.

## Security and Abuse Controls

- Limit imported dictionary size, entry count, regex count, and timed-effects extremes.
- Server-side sanitize/validate metadata fields (`name`, `description`, `tags`, `category`).
- Rate-limit share creation/import endpoints.
- Audit every share policy mutation and import event.
- Add denylist hooks for known malicious regex/content signatures.

## Rollout Plan

1. Backend contracts + flags
   - Add tables/endpoints behind `chat_dictionary_sharing_enabled`.
2. Owner-only UI controls
   - Share policy modal + revoke actions.
3. Import-from-share UX
   - Preview + explicit copy semantics.
4. Team/public gallery
   - Incremental release after moderation/audit checks pass.

## Rollout Checklist (Feature Flags + Migration Guards)

- [ ] Enable schema migrations for sharing tables only after backup snapshot completes.
- [ ] Keep sharing endpoints behind `chat_dictionary_sharing_enabled` (default `false`).
- [ ] Gate public gallery behind separate `chat_dictionary_public_gallery_enabled`.
- [ ] Validate include graph (`included_dictionary_ids`) before enabling cross-owner includes.
- [ ] Verify rollback path: disable flags without breaking existing private dictionary CRUD.
- [ ] Confirm audit events for policy create/update/revoke/import are emitted.
- [ ] Confirm rate limits applied to share creation/import endpoints.

## Success Metrics

- Share adoption: number of dictionaries with active share policies.
- Import conversion: share views -> imports.
- Safety: rejected imports (validation), regex risk blocks, moderation actions.
- Reliability: share endpoint error rate and policy-conflict rate.
- Template adoption: % of created dictionaries that start from a starter template.
- Shortcut usage: count of `new_dictionary`, `submit_form`, and `run_validation` shortcut-triggered actions.
- Revert events: count of successful dictionary revision reverts over time.
