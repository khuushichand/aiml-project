# Quick Ingest Audio Dropdowns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the quick-ingest wizard's audio language and transcription model text inputs with a standard-language dropdown plus custom fallback, and a backend-backed transcription model dropdown, in the shared UI used by both the WebUI and extension.

**Architecture:** Keep the change in the shared quick-ingest configure step so `apps/tldw-frontend` and `apps/extension` stay in parity. Reuse the frontend-owned language list from `SUPPORTED_LANGUAGES`, preserve nonstandard saved values through a custom-language path, and fetch transcription models from the existing `/api/v1/media/transcription-models` endpoint without changing backend contracts.

**Tech Stack:** React 18, TypeScript, Ant Design `Select`/`Input`, Vitest, Testing Library, shared `@/services/tldw/TldwApiClient`

---

## File Map

- Modify: `apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx`
  Responsibility: replace the current freeform audio language/model inputs with structured controls, preserve current values, and keep disabled-state behavior unchanged when no audio/video items exist.
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx`
  Responsibility: cover the new language-dropdown/custom-input path and backend-backed transcription model dropdown behavior.
- Reference only: `apps/packages/ui/src/utils/supported-languages.ts`
  Responsibility: existing source for standard language dropdown options.
- Reference only: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
  Responsibility: existing `getTranscriptionModels()` client call for the backend model catalog.
- Reference only: `Docs/superpowers/specs/2026-03-25-quick-ingest-audio-dropdowns-design.md`
  Responsibility: approved behavior contract for implementation.

## Implementation Notes

- Do not add a backend endpoint. The model dropdown must consume the existing `/api/v1/media/transcription-models` contract.
- Do not move quick-ingest state to a new store shape. Continue writing language to `typeDefaults.audio.language` and the selected model to `advancedValues.transcription_model`.
- Preserve unknown existing values:
  - language: route unknown saved values through the custom-language input
  - model: append the current value to rendered options if the server catalog does not include it
- Keep the existing disabled-state rule:
  - audio language, custom language input, diarization, and model select remain disabled when the queue has no audio/video items

### Task 1: Add Red Tests For Structured Audio Language Selection

**Files:**
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx`

- [ ] **Step 1: Write the failing test for standard language selection and custom fallback**

Add integration coverage in `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx` for both of these behaviors:

```tsx
it("uses a searchable language select and stores a standard language value", async () => {
  render(<QuickIngestWizardModal open onClose={vi.fn()} />)

  await queueVideoAndOpenConfigureStep()

  const languageSelect = await screen.findByLabelText("Audio language")
  await user.selectOptions(languageSelect, "en-US")

  expect(languageSelect).toHaveValue("en-US")
  expect(screen.queryByLabelText("Custom audio language")).not.toBeInTheDocument()
})

it("switches to custom language input when the saved value is not in the standard list", async () => {
  seedWizardWithAudioLanguage("xx-custom")
  render(<QuickIngestWizardModal open onClose={vi.fn()} />)

  await queueVideoAndOpenConfigureStep()

  expect(await screen.findByLabelText("Audio language")).toHaveValue("__custom__")
  expect(screen.getByLabelText("Custom audio language")).toHaveValue("xx-custom")
})
```

- [ ] **Step 2: Run the test to verify it fails for the right reason**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
npm run test:run -- ../packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx -t "language"
```

Expected:
- FAIL because the configure step still renders a plain text `Input`
- FAIL because there is no custom-language sentinel path yet

- [ ] **Step 3: Write the minimal language-selector implementation**

In `apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx`, replace the plain language `Input` with a `Select` plus conditional custom `Input`.

Implementation shape:

```tsx
const CUSTOM_LANGUAGE_VALUE = "__custom__"

const standardLanguageOptions = React.useMemo(
  () => [
    ...SUPPORTED_LANGUAGES,
    { value: CUSTOM_LANGUAGE_VALUE, label: qi("customLanguageOption", "Custom language...") },
  ],
  [qi]
)

const savedAudioLanguage = String(presetConfig.typeDefaults.audio?.language || "").trim()
const hasStandardLanguage = standardLanguageOptions.some(
  (option) => String(option.value) === savedAudioLanguage
)
const languageSelectValue =
  !savedAudioLanguage ? undefined : hasStandardLanguage ? savedAudioLanguage : CUSTOM_LANGUAGE_VALUE
const showCustomLanguageInput = languageSelectValue === CUSTOM_LANGUAGE_VALUE
```

Then wire handlers so:

- selecting a standard option writes that exact value into `typeDefaults.audio.language`
- selecting `CUSTOM_LANGUAGE_VALUE` leaves the real saved value unchanged until the user edits the custom input
- editing the custom input writes the trimmed value or `undefined`

- [ ] **Step 4: Run the language test again to verify it passes**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
npm run test:run -- ../packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx -t "language"
```

Expected:
- PASS for the new language-select and custom-language cases

- [ ] **Step 5: Commit the language-selector slice**

```bash
git add apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx
git commit -m "feat: add structured quick ingest language selection"
```

### Task 2: Add Red Tests For Backend-Driven Transcription Model Selection

**Files:**
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx`

- [ ] **Step 1: Write the failing test for server-provided model options and unknown-value preservation**

Extend the quick-ingest integration test file so the mocked `tldwClient` returns a model catalog, then assert both the normal and fallback behaviors:

```tsx
it("loads transcription models from the backend catalog", async () => {
  mockGetTranscriptionModels.mockResolvedValue({
    all_models: ["whisper-large-v3", "parakeet-standard"],
  })

  render(<QuickIngestWizardModal open onClose={vi.fn()} />)
  await queueVideoAndOpenConfigureStep()

  const modelSelect = await screen.findByLabelText("Transcription model")
  expect(screen.getByRole("option", { name: "whisper-large-v3" })).toBeInTheDocument()
  expect(screen.getByRole("option", { name: "parakeet-standard" })).toBeInTheDocument()
})

it("preserves a current transcription model that is not returned by the backend catalog", async () => {
  seedWizardWithTranscriptionModel("provider/custom-model")
  mockGetTranscriptionModels.mockResolvedValue({
    all_models: ["whisper-large-v3"],
  })

  render(<QuickIngestWizardModal open onClose={vi.fn()} />)
  await queueVideoAndOpenConfigureStep()

  expect(await screen.findByDisplayValue("provider/custom-model")).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the model test to verify it fails correctly**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
npm run test:run -- ../packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx -t "transcription model"
```

Expected:
- FAIL because the configure step still renders a text `Input`
- FAIL because it does not fetch or render backend model options

- [ ] **Step 3: Implement the backend-backed model dropdown**

In `apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx`, add a local fetch effect or reuse the existing `useTranscriptionModelsCatalog` pattern so the component loads backend models only when the configure step is open for audio/video content.

Implementation shape:

```tsx
const [transcriptionModelOptions, setTranscriptionModelOptions] = React.useState<SelectOption[]>([])
const [transcriptionModelsLoading, setTranscriptionModelsLoading] = React.useState(false)

React.useEffect(() => {
  if (!hasTranscriptionItems) return
  let cancelled = false

  const loadModels = async () => {
    setTranscriptionModelsLoading(true)
    try {
      const result = await tldwClient.getTranscriptionModels()
      const unique = Array.from(new Set(Array.isArray(result?.all_models) ? result.all_models : []))
      const options = unique.map((model) => ({ value: model, label: model }))
      const withCurrent = ensureCurrentValue(options, currentModel)
      if (!cancelled) setTranscriptionModelOptions(withCurrent)
    } finally {
      if (!cancelled) setTranscriptionModelsLoading(false)
    }
  }

  void loadModels()
  return () => {
    cancelled = true
  }
}, [hasTranscriptionItems, currentModel])
```

Then replace the model `Input` with a searchable `Select` that:

- uses backend-loaded options
- appends the current value if the backend does not include it
- stays disabled when `hasTranscriptionItems` is false

- [ ] **Step 4: Run the model test again to verify it passes**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
npm run test:run -- ../packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx -t "transcription model"
```

Expected:
- PASS for backend model rendering
- PASS for preserving unknown current values

- [ ] **Step 5: Commit the model-dropdown slice**

```bash
git add apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx
git commit -m "feat: add backend-driven quick ingest model dropdown"
```

### Task 3: Run Regression Verification On The Shared Wizard Slice

**Files:**
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx`

- [ ] **Step 1: Add or adjust regression assertions for the existing disabled-state and video-only behavior**

Keep or extend the existing integration tests so these still hold:

```tsx
expect(screen.getByLabelText("Audio language")).not.toBeDisabled()
expect(screen.getByLabelText("Audio diarization toggle")).not.toBeDisabled()
expect(screen.getByLabelText("Transcription model")).not.toBeDisabled()
```

and for non-audio/video batches:

```tsx
expect(screen.getByLabelText("Audio language")).toBeDisabled()
expect(screen.getByLabelText("Transcription model")).toBeDisabled()
```

- [ ] **Step 2: Run the full targeted quick-ingest integration test file**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
npm run test:run -- ../packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx
```

Expected:
- PASS for the full quick-ingest integration suite

- [ ] **Step 3: Run lint on the touched shared UI files**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
npm run lint -- ../packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx ../packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx
```

Expected:
- PASS with no new lint errors in the touched files

- [ ] **Step 4: Record verification notes before completion**

Document in the execution notes:

- targeted Vitest file passed
- lint passed for touched files
- Bandit not applicable because the touched scope is TypeScript-only and introduces no Python code

- [ ] **Step 5: Commit the verification cleanup**

```bash
git add apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx
git commit -m "test: cover quick ingest audio dropdown regressions"
```
