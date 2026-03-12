# `/tts` Speech Playground Reuse Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/tts` reuse the redesigned `SpeechPlaygroundPage` in TTS-only mode instead of rendering the legacy `TtsPlaygroundPage`.

**Architecture:** Repoint the shared `/tts` route to `SpeechPlaygroundPage`, then add an explicit locked-mode contract so the shared page can behave as a dedicated TTS entrypoint without mutating or depending on the remembered multi-mode state used by `/speech`. Keep `/speech` unchanged and leave `TtsPlaygroundPage` in place as an unused follow-up cleanup candidate.

**Tech Stack:** React, TypeScript, React Router shared route layer, Next.js dynamic page shim, Vitest, Testing Library

---

### Task 1: Add Locked-Mode Support To `SpeechPlaygroundPage`

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx:201-227`
- Modify: `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx:1688-1711`
- Modify: `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx:1964-2230`
- Modify: `apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx:1-320`

**Step 1: Write the failing test**

Add render coverage for locked and unlocked behavior. The locked-mode tests must prove both visible behavior and persisted-state safety.

```tsx
const setSpeechModeMock = vi.fn()

it("hides the mode switcher and STT region when locked to listen mode", () => {
  render(<SpeechPlaygroundPage lockedMode="listen" hideModeSwitcher />)

  expect(screen.queryByText("Mode")).not.toBeInTheDocument()
  expect(screen.queryByText("Current transcription model")).not.toBeInTheDocument()
  expect(screen.getByTestId("tts-provider-strip")).toBeInTheDocument()
})

it("does not overwrite stored mode when locked mode is provided", () => {
  render(<SpeechPlaygroundPage lockedMode="listen" hideModeSwitcher />)

  expect(setSpeechModeMock).not.toHaveBeenCalled()
})

it("keeps the mode switcher visible when unlocked", () => {
  render(<SpeechPlaygroundPage />)

  expect(screen.getByText("Mode")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `./node_modules/.bin/vitest run src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx`

Expected: FAIL because `SpeechPlaygroundPage` does not yet accept `lockedMode`, does not hide the mode picker, and still mutates the remembered mode path through the current effect.

**Step 3: Write minimal implementation**

Add explicit locked-mode props and derive a route-safe effective mode.

```tsx
type SpeechPlaygroundPageProps = {
  initialMode?: SpeechMode
  lockedMode?: SpeechMode
  hideModeSwitcher?: boolean
}

const effectiveMode = lockedMode ?? mode

React.useEffect(() => {
  if (lockedMode) return
  if (initialMode && mode !== initialMode) {
    setMode(initialMode)
  }
}, [initialMode, lockedMode, mode, setMode])

const handleModeChange = (value: SpeechMode) => {
  if (lockedMode) return
  setMode(value)
}
```

Use `effectiveMode` instead of `mode` for all mode-dependent behavior, not just the outer JSX. At minimum, cover:

- the segmented control value/change handler
- the keyboard-shortcut effect
- layout branching
- STT/TTS region gating
- round-trip-only controls

Do not rename the existing enum values in this task.

**Step 4: Run test to verify it passes**

Run: `./node_modules/.bin/vitest run src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx`

Expected: PASS, with locked `/tts`-style rendering suppressing non-TTS UI and leaving the remembered mode setter untouched.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx
git commit -m "feat(ui): support route-locked speech playground mode"
```

### Task 2: Rewire The `/tts` Route To The Shared Speech Playground

**Files:**
- Modify: `apps/packages/ui/src/routes/option-tts.tsx:1-20`
- Modify: `apps/packages/ui/src/routes/__tests__/option-audio-route-identity.test.tsx:1-140`
- Reference: `apps/packages/ui/src/routes/option-speech.tsx:1-15`
- Reference: `apps/tldw-frontend/pages/tts.tsx:1-3`

**Step 1: Write the failing tests**

Update the route identity test so `/tts` expects the shared speech page instead of the legacy TTS page. Extend the mock to surface route-lock props and preserve route error boundary coverage.

```tsx
vi.mock("@/components/Option/Speech/SpeechPlaygroundPage", () => ({
  __esModule: true,
  default: ({
    initialMode,
    lockedMode,
    hideModeSwitcher,
  }: {
    initialMode?: string
    lockedMode?: string
    hideModeSwitcher?: boolean
  }) => (
    <div
      data-testid="speech-playground"
      data-mode={initialMode ?? "roundtrip"}
      data-locked-mode={lockedMode ?? ""}
      data-hide-mode-switcher={hideModeSwitcher ? "true" : "false"}
    >
      Speech
    </div>
  ),
}))

it("routes /tts into the shared speech playground locked to TTS mode", () => {
  render(<OptionTts />)
  const speech = screen.getByTestId("speech-playground")
  expect(speech).toHaveAttribute("data-locked-mode", "listen")
  expect(speech).toHaveAttribute("data-hide-mode-switcher", "true")
  expect(screen.queryByTestId("tts-playground")).not.toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `./node_modules/.bin/vitest run src/routes/__tests__/option-audio-route-identity.test.tsx`

Expected: FAIL because `OptionTts` still renders `TtsPlaygroundPage`.

**Step 3: Write minimal implementation**

Replace the legacy import in `option-tts.tsx` with the shared page, and wrap it in the same `RouteErrorBoundary` pattern used by `/speech`.

```tsx
import OptionLayout from "~/components/Layouts/Layout"
import SpeechPlaygroundPage from "@/components/Option/Speech/SpeechPlaygroundPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionTts = () => {
  return (
    <RouteErrorBoundary routeId="tts" routeLabel="TTS Playground">
      <OptionLayout>
        <SpeechPlaygroundPage lockedMode="listen" hideModeSwitcher />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
```

Do not change `apps/tldw-frontend/pages/tts.tsx`; it should continue importing the shared route module.

**Step 4: Run test to verify it passes**

Run: `./node_modules/.bin/vitest run src/routes/__tests__/option-audio-route-identity.test.tsx`

Expected: PASS, with `/tts` now mapped to the shared speech playground and `/speech` still mapped to the unlocked route.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/option-tts.tsx apps/packages/ui/src/routes/__tests__/option-audio-route-identity.test.tsx
git commit -m "refactor(ui): route /tts through shared speech playground"
```

### Task 3: Verify The Shared Entry Point And Guard Against Regressions

**Files:**
- Verify: `apps/packages/ui/src/routes/option-tts.tsx`
- Verify: `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx`
- Verify: `apps/packages/ui/src/routes/__tests__/option-audio-route-identity.test.tsx`
- Verify: `apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx`
- Reference only: `apps/tldw-frontend/pages/tts.tsx`

**Step 1: Run the focused route and render suites together**

```bash
cd apps/packages/ui
./node_modules/.bin/vitest run \
  src/routes/__tests__/option-audio-route-identity.test.tsx \
  src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx
```

Expected: PASS for both files.

**Step 2: Inspect the working tree**

Run: `git diff -- apps/packages/ui/src/routes/option-tts.tsx apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx apps/packages/ui/src/routes/__tests__/option-audio-route-identity.test.tsx apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx`

Expected: only the route reuse, locked-mode logic, and matching tests.

**Step 3: Optional smoke check**

If a local frontend runner is already available, open `/tts` and confirm:

- the new Speech Playground TTS UI is visible
- the mode switcher is hidden on `/tts`
- `/speech` still shows the mode switcher

If no runner is available, record that the change was verified by tests only.

**Step 4: Final commit**

```bash
git add apps/packages/ui/src/routes/option-tts.tsx apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx apps/packages/ui/src/routes/__tests__/option-audio-route-identity.test.tsx apps/packages/ui/src/components/Option/Speech/__tests__/SpeechPlaygroundPage.render.test.tsx
git commit -m "test(ui): lock /tts onto redesigned speech playground"
```

**Step 5: Completion note**

Document in the implementation summary that `TtsPlaygroundPage` is intentionally left in place as an unused follow-up cleanup candidate.
