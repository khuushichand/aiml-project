# Quick Ingest Audio Dropdowns Design

Date: 2026-03-25
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Replace the quick-ingest wizard's freeform audio language and transcription model inputs with structured controls in the shared UI package so both the WebUI and extension stay aligned.

The language control should use a standard frontend-maintained language list plus a `Custom language...` path for arbitrary values. The transcription model control should use the backend's existing `/api/v1/media/transcription-models` response so the wizard exposes the same model options the server already advertises.

## Problem

The current quick-ingest configure step uses plain text inputs for two fields that behave like constrained choices:

- [`WizardConfigureStep.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx) renders `Audio language` as a freeform text input.
- The same step renders `Transcription model` as a freeform text input.

This creates three product issues:

- users do not discover the available server-supported transcription models
- users are forced to guess or memorize language codes
- the UI encourages invalid or inconsistent values even though the backend already validates transcription models against a known set

Because the quick-ingest wizard is shared under `apps/packages/ui/src`, this inconsistency affects both the Next.js WebUI and the browser extension.

## Goals

- Replace the audio language text input with a structured dropdown.
- Keep language selection fast for common cases while still allowing arbitrary custom input.
- Replace the transcription model text input with a searchable dropdown populated from the backend.
- Preserve unknown or previously saved values instead of silently dropping them.
- Keep the change inside the shared wizard so WebUI and extension behavior stays in parity.
- Avoid introducing a new backend endpoint when the current backend contracts are already sufficient.

## Non-Goals

- Make the language list backend-driven.
- Redesign the full quick-ingest wizard flow.
- Change ingest payload field names or backend validation rules.
- Add per-provider language filtering logic in this pass.
- Remove support for manually entering nonstandard language tags or provider-specific model ids.

## Current State

### Shared wizard surface

The active quick-ingest flow is the shared wizard modal:

- [`QuickIngestWizardModal.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/QuickIngestWizardModal.tsx)
- [`WizardConfigureStep.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx)

The configure step already exposes:

- common ingest toggles
- audio diarization
- document OCR
- video captions
- storage and review toggles

The audio language and transcription model controls are the only audio-option fields still using raw text entry.

### Existing option sources

The codebase already has the right source material for both controls:

- frontend standard language list:
  - [`supported-languages.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/utils/supported-languages.ts)
- backend transcription model catalog:
  - [`transcription_models.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/Ingestion_Media_Processing/transcription_models.py)
  - exposed through [`transcription_models.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/media/transcription_models.py)
- shared client helper:
  - [`TldwApiClient.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/services/tldw/TldwApiClient.ts)

The shared UI also already contains server-model fetch patterns in:

- [`useTranscriptionModelsCatalog.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useTranscriptionModelsCatalog.ts)
- [`SSTSettings.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Settings/SSTSettings.tsx)

## Proposed Design

### 1. Keep the change in the shared wizard configure step

The write target remains:

- [`WizardConfigureStep.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx)

This preserves parity across:

- `apps/tldw-frontend`
- `apps/extension`

No platform-specific UI fork should be introduced for this change.

### 2. Audio language becomes a structured dropdown with a custom path

The `Audio language` control should become an Ant Design `Select` with search enabled.

Primary option source:

- the shared `SUPPORTED_LANGUAGES` list from [`supported-languages.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/utils/supported-languages.ts)

Additional option:

- a sentinel option labeled `Custom language...`

Behavior rules:

- selecting a standard language stores its value directly in `presetConfig.typeDefaults.audio.language`
- selecting `Custom language...` reveals a text input directly below the dropdown
- the custom text input stores the freeform value in the same `typeDefaults.audio.language` field
- clearing the custom text input should resolve to `undefined`, not an empty string

The control must also handle existing state safely:

- if the current saved value matches one of the standard dropdown options, show it as the selected dropdown value
- if the current saved value does not match a standard option, automatically switch the UI into `Custom language...` mode and prefill the text input with that saved value

This preserves compatibility with:

- existing stored wizard state
- copied language codes like `en`
- locale-style values like `en-US`
- provider-specific or user-entered tags not present in the standard list

### 3. Transcription model becomes a searchable backend-backed dropdown

The `Transcription model` control should become an Ant Design `Select` with search enabled.

Source of truth:

- `GET /api/v1/media/transcription-models`

The wizard should use the existing shared client call:

- [`TldwApiClient.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/services/tldw/TldwApiClient.ts)

Behavior rules:

- on configure-step render, fetch the server model catalog when the ingest connection is online
- flatten `all_models` into unique dropdown options
- use the model id as both `value` and fallback label
- keep the control disabled when there are no audio or video items, matching the current rule

Failure and fallback rules:

- if the backend call fails, do not block the step
- if a saved or preset value exists, include that value as an option so it remains visible and selectable
- if the fetch succeeds but the current value is not in the returned catalog, append the current value as an extra option rather than erasing it

This keeps the UI honest without making previously stored values disappear.

### 4. Presets and custom settings continue to work through the same state field

The change should not introduce a parallel state model.

The wizard should continue using:

- `typeDefaults.audio.language`
- `advancedValues.transcription_model`

Preset detection and custom-setting detection should continue to behave as they do now:

- standard language selection updates `typeDefaults.audio.language`
- custom language input updates the same field
- model dropdown selection updates `advancedValues.transcription_model`

No backend payload shape changes are needed.

### 5. UX details

The configure step should use this interaction model:

- `Audio language`
  - searchable dropdown
  - standard languages first
  - `Custom language...` as the final option
- `Custom language`
  - shown only when the sentinel option is active or when the current saved value is nonstandard
- `Transcription model`
  - searchable dropdown
  - loading state while model catalog is being fetched
  - preserved current value when server data is missing or incomplete

Accessibility requirements:

- keep stable `aria-label` coverage for the language and transcription model controls
- expose the custom-language input with its own label when visible
- keep the controls keyboard-accessible in the modal without introducing hidden focus traps

### 6. No new backend endpoint is required

Backend work is intentionally out of scope for this change.

Reasoning:

- the language source is intentionally frontend-owned
- the model catalog endpoint already exists and is already used in shared UI

This makes the implementation smaller and reduces rollout risk for both the WebUI and extension.

## Testing

### Unit and integration coverage

Update quick-ingest wizard tests under `apps/packages/ui/src/components/Common/QuickIngest/__tests__/` to cover:

- standard language selection writes the chosen language value
- nonstandard saved language values render through the custom-language path
- switching to `Custom language...` reveals the text input
- clearing a custom language removes the stored value
- model dropdown loads backend-provided options
- unknown current transcription model values remain visible after model fetch

### Existing behavior guards

Retain coverage for:

- video-only batches enabling audio defaults
- disabled audio controls when the queue has no audio or video items
- preset switching still reflecting custom-settings state correctly

### Optional browser-level follow-up

If the existing quick-ingest E2E coverage becomes brittle around Ant Design select behavior, add or update one shared browser test helper assertion so the configure step verifies:

- the transcription model control is present as a selectable field
- the language control is present as a selectable field

That follow-up is optional unless current browser tests regress.

## Risks and Mitigations

### Risk: standard language list uses locale-style values, while users may expect short codes

Mitigation:

- preserve custom input for short or provider-specific codes
- do not restrict input to the standard dropdown list only

### Risk: backend model endpoint returns a broader static catalog than what is currently installed

Mitigation:

- this is acceptable for the current request because the requirement is to expose backend-advertised options
- preserve the existing health-check and validation behavior elsewhere rather than overfitting the wizard to installation state

### Risk: saved values disappear when they do not match returned dropdown options

Mitigation:

- explicitly append unknown current values into the rendered option list
- auto-route nonstandard language values into the custom-language path

## Result

After this change, the quick-ingest configure step will expose structured audio language and transcription model selection without losing flexibility:

- users can pick common languages quickly
- users can still enter arbitrary custom language tags when needed
- users can see the backend's available transcription-model catalog without guessing model ids
- both the WebUI and extension get the same behavior from the shared wizard surface
