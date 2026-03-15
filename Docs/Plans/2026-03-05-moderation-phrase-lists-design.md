# Moderation UX Design: Per-User Banlist/Notify Phrase Lists

- Date: 2026-03-05
- Status: Approved
- Scope: WebUI + extension moderation page UX, plus backend schema/service support for per-user phrase rules

## Problem

The moderation page currently requires users to manually author full rule syntax lines (for example `phrase -> block`) to add individual items. This is high-friction for common workflows:

- Add a single banned word/phrase
- Add a single notify phrase

We want this to be easy from the default moderation experience, not hidden behind advanced/raw editors.

## Goals

1. Make adding individual words/phrases quick and obvious.
2. Support both list intents:
- Banlist -> enforced as `block`
- Notify list -> enforced as `warn`
3. Support per-user phrase rules in User scope.
4. Keep existing advanced/global blocklist tooling intact.
5. Preserve existing save model (explicit Save override; no silent auto-save).

## Non-Goals

1. Replacing existing global managed blocklist or raw file editor.
2. Introducing a new moderation action type (notify maps to existing `warn`).
3. Full rule-engine UI overhaul for all moderation features.

## Product Decisions (Validated)

1. Notify list maps to action `warn`.
2. Quick add controls are visible in the main non-advanced moderation view.
3. Phrase composer defaults to literal matching, with optional regex toggle.
4. Per-user quick add is supported in User scope (requires backend support).
5. New per-user quick-added rules apply to both input and output by default.

## UX Design

### New Card: User Phrase Lists

Add a new card in the main moderation screen (visible without Advanced mode):

- Title: `User Phrase Lists`
- Visible in all scopes, but active controls require `User (Individual)` scope and a loaded user ID.
- In Server scope, show guidance CTA: switch to User scope and load a user.

### Quick Rule Composer

Controls:

- Text input: phrase or regex
- List selector: `Banlist` | `Notify list`
- Toggle: `Regex` (default off)
- Primary action: `Add`

Behavior:

- Banlist adds rule with action `block`
- Notify list adds rule with action `warn`
- Rule phase defaults to `both` (input + output)
- Added item appears immediately in draft lists and marks override as dirty

### List Display

Show two compact sections in the card:

- `Banned phrases`
- `Notify phrases`

Each row includes:

- Phrase preview
- Badges (`Literal`/`Regex`, `Both phases`)
- Remove action

### Save UX

- Reuse existing `Save override` flow and dirty indicators.
- Keep keyboard shortcut behavior (`Ctrl/Cmd+S`).
- No background auto-save.

## Data Model Design

## Per-user rule model

Extend per-user override payload with optional `rules`:

```json
{
  "rules": [
    {
      "id": "uuid-or-stable-id",
      "pattern": "sensitive phrase",
      "is_regex": false,
      "action": "block",
      "phase": "both"
    }
  ]
}
```

Field notes:

- `id`: UI-stable id for editing/removal
- `pattern`: raw phrase or regex source
- `is_regex`: `false` for default literal flow
- `action`: `block` or `warn` for this feature
- `phase`: defaults to `both` (future extension-ready)

Backward compatibility:

- Existing overrides without `rules` remain valid.
- Existing override fields are unchanged.

## Architecture and Data Flow

1. User adds phrase in moderation UI quick composer.
2. UI translates selection into normalized rule object.
3. Rule appended to `overrideDraft.rules` in client state.
4. On `Save override`, `setUserOverride(user_id, payload)` sends rules with other override settings.
5. Backend validates and persists rules in override storage.
6. Effective policy resolution merges global blocklist rules + per-user rules.
7. `testModeration` and normal moderation evaluation use merged effective rules.

## Backend Changes

1. Schemas
- Extend moderation user override schema to accept and validate `rules[]`.
- Validate action (`block|warn` for quick flow; optionally accept existing rule actions if needed by system policy).
- Validate phase enum (`input|output|both`).

2. Service
- Extend effective policy assembly to include per-user rule set.
- Compile user rules to runtime pattern rules with correct action mapping.
- Ensure per-user rules are additive to global rules (not replacing global blocklist).

3. Policy snapshot/test responses
- Ensure snapshots and counts reflect merged rules.
- Ensure test endpoint behavior reflects per-user quick-added rules immediately after save.

## Validation and Error Handling

UI validation:

- Reject empty phrase.
- Reject duplicate within current user list (same pattern + regex flag + action + phase).
- Basic regex validation when `Regex=true`.

Backend validation:

- Reject malformed regex.
- Reject invalid action/phase.
- Return HTTP 400 with actionable details.

Failure behavior:

- Preserve unsaved draft on save failure.
- Surface precise inline or toast error.

## Testing Strategy

### Backend unit tests

1. Override schema accepts/rejects `rules` correctly.
2. Effective policy merges global + per-user rules.
3. `phase=both` applies to both input and output.
4. Banlist/notify mapping executes as `block`/`warn`.

### API tests

1. `PUT/GET /moderation/users/{id}` roundtrip with rules.
2. `POST /moderation/test` reflects per-user rules for same user.

### UI tests

1. Quick add appears in non-advanced moderation page.
2. In User scope, adding ban/notify phrase populates correct list.
3. Removing an item updates draft and dirty state.
4. Save payload includes `rules`.

## Rollout Notes

1. Ship without removing advanced editors.
2. Keep raw blocklist editor for power users.
3. Add helper copy explaining: notify list logs warnings but allows content.

## Risks and Mitigations

1. Risk: rule duplication/confusion between global and per-user layers.
- Mitigation: clear card labeling and policy summary hints.

2. Risk: regex misuse by users.
- Mitigation: literal-by-default and regex validation.

3. Risk: backward compatibility for existing override files.
- Mitigation: optional `rules` field and defensive parsing.

## Acceptance Criteria

1. A user can add a banned phrase in <=3 interactions from main moderation view.
2. A user can add a notify phrase in <=3 interactions from main moderation view.
3. Rules are persisted per user and enforced in moderation test/results.
4. Existing advanced/global moderation flows continue functioning.
