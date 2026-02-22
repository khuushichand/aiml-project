# Implementation Plan: Chat Dictionaries - Probability and Timed Effects Configuration

## Scope

Components: entry creation/edit UI in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`, timed-effects schema in `tldw_Server_API/app/api/v1/schemas/chat_dictionary_schemas.py`, transform behavior docs and tests
Finding IDs: `3.1` through `3.4`

## Finding Coverage

- Probability control clarity and affordance: `3.1`
- Timed-effects configurability gap: `3.2`
- Conceptual guidance for overlapping controls: `3.3`
- Case sensitivity default behavior and user expectation: `3.4`

## Stage 1: Timed Effects UI and Payload Plumbing
**Goal**: Expose full timed-effects capability in entry authoring workflows.
**Success Criteria**:
- Add and edit entry surfaces include `sticky`, `cooldown`, and `delay` fields.
- Fields are labeled in seconds and support `0` as disabled semantics.
- UI values map cleanly to backend `TimedEffects` model without lossy transforms.
- Advanced section state is preserved when toggling simple/advanced mode.
**Tests**:
- Component tests for timed-effects field validation and default values.
- Integration tests for create/edit requests carrying timed-effects payload.
- API tests ensuring persisted values are returned consistently by list/get entry endpoints.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Timed-effects fields (`sticky`, `cooldown`, `delay`) are present in both add-entry advanced mode and edit-entry modal with explicit seconds labels and `0`-means-disabled help text.
- Added component test coverage to verify timed-effects values persist when toggling add-entry simple/advanced mode.
- Added endpoint round-trip coverage asserting timed-effects values are returned consistently by add/list/get dictionary entry APIs.
- Existing add/edit entry tests continue to validate timed-effects payload plumbing in UI mutation requests.

## Stage 2: Probability UX and Mental Model Guidance
**Goal**: Make probabilistic behavior intuitive and less error-prone.
**Success Criteria**:
- Probability input pairs numeric field with slider for fast adjustment.
- Helper copy translates decimal into approximate frequency language.
- `max_replacements` help text explicitly distinguishes from probability gating.
- Form validation prevents out-of-range values and clarifies boundary behavior.
**Tests**:
- Component tests for synchronized slider/input behavior.
- Copy regression tests for probability vs max-replacements guidance text.
- Integration tests confirming boundary values (`0`, `1`) serialize correctly.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Added probability sliders alongside numeric probability inputs in both add-entry advanced mode and edit-entry modal.
- Added dynamic helper text translating probability to frequency language (`Fires ~N out of 10 messages`).
- Added explicit probability range validation messaging (`0` to `1`) on both add and edit forms.
- Updated max-replacements help copy to clearly separate gating (`probability`) from per-message cap (`max_replacements`).
- Added component coverage for probability guidance rendering and boundary interaction through form input updates.

## Stage 3: Sensible Defaults and Backward Compatibility
**Goal**: Reduce surprise for common use cases while preserving compatibility.
**Success Criteria**:
- UI default for `case_sensitive` is explicitly set and documented.
- Migration note clarifies legacy behavior when value is omitted by old clients.
- Existing entries without explicit `case_sensitive` continue to load safely.
**Tests**:
- Unit tests for default initialization logic in add-entry form.
- API compatibility tests for omitted vs explicit case-sensitivity fields.
- Regression tests for update flows from previously stored entries.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Add-entry flow now sets an explicit UI default of `case_sensitive=false` when users do not choose a value.
- Add-entry advanced form switch now initializes case sensitivity as off to match common text-replacement expectations.
- Added UI test coverage ensuring default add-entry submissions send `case_sensitive: false`.
- Added backend endpoint compatibility test verifying omitted case-sensitivity remains server-default `true` while explicit `false` remains honored.

## Dependencies

- Timed-effects semantics should remain aligned with chat dictionary processing logic in `ChatDictionaryService`.
- Guidance copy should align with validation/help text used in Category 4.
