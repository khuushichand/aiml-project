# Workspace Playground Studio Output Failure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/workspace-playground` studio outputs fail honestly, download through the correct per-artifact path, and preserve valid success flows.

**Architecture:** Keep the fix inside the shared `StudioPane` pipeline instead of scattering special cases across the page. First lock the broken behavior with focused `StudioPane.stage1` tests, then add typed result finalization plus helper-level failure propagation, then make download routing artifact-aware so quiz and audio flows cannot claim success through the wrong path.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, Ant Design, browser Blob/URL APIs

**Status:** Complete

---

### Task 1: Guard Text-Like Studio Outputs Against Invalid RAG Results

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`

**Step 1: Write the failing tests**

Add focused tests for missing and sentinel content before touching implementation. Keep them in `StudioPane.stage1.test.tsx` near the existing generation lifecycle tests.

```ts
it("marks summary artifacts failed when ragSearch returns no usable content", async () => {
  mockRagSearch.mockResolvedValue({ generation: "", answer: "" })

  renderStudioPane()
  fireEvent.click(screen.getByRole("button", { name: "Summary" }))

  await waitFor(() => {
    expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
      "artifact-1",
      "failed",
      expect.objectContaining({
        errorMessage: expect.stringContaining("usable summary")
      })
    )
  })

  expect(mockMessageSuccess).not.toHaveBeenCalled()
})

it("marks summary artifacts failed when ragSearch returns the local failure sentinel", async () => {
  mockRagSearch.mockResolvedValue({ generation: "Summary generation failed" })

  renderStudioPane()
  fireEvent.click(screen.getByRole("button", { name: "Summary" }))

  await waitFor(() => {
    expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
      "artifact-1",
      "failed",
      expect.objectContaining({
        errorMessage: expect.stringContaining("usable summary")
      })
    )
  })

  expect(mockMessageSuccess).not.toHaveBeenCalled()
})

it("still completes valid summary artifacts", async () => {
  mockRagSearch.mockResolvedValue({ generation: "Generated summary" })

  renderStudioPane()
  fireEvent.click(screen.getByRole("button", { name: "Summary" }))

  await waitFor(() => {
    expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
      "artifact-1",
      "completed",
      expect.objectContaining({
        content: "Generated summary"
      })
    )
  })

  expect(mockMessageSuccess).toHaveBeenCalledWith(
    expect.stringContaining("generated successfully")
  )
})
```

**Step 2: Run the tests to verify they fail**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx -t "marks summary artifacts failed"`

Expected: FAIL because `handleGenerateOutput` currently treats empty or sentinel text as successful content and calls the success toast path.

**Step 3: Write the minimal implementation**

Add a typed finalization path in `StudioPane/index.tsx` and stop returning local fallback failure strings from the RAG helper functions.

```ts
const TEXT_FAILURE_SENTINELS: Partial<Record<ArtifactType, string[]>> = {
  summary: ["Summary generation failed"],
  report: ["Report generation failed"],
  compare_sources: ["Compare sources generation failed"],
  timeline: ["Timeline generation failed"],
  mindmap: ["Mind map generation failed"],
  slides: ["Slides generation failed"],
  data_table: ["Data table generation failed"]
}

const requireUsableTextResult = (
  type: ArtifactType,
  result: GenerationResult,
  errorMessage: string
): GenerationResult => {
  const content = typeof result.content === "string" ? result.content.trim() : ""
  const sentinels = TEXT_FAILURE_SENTINELS[type] ?? []

  if (!content || sentinels.includes(content)) {
    throw new Error(errorMessage)
  }

  return {
    ...result,
    content
  }
}

const finalizeGenerationResult = (
  type: ArtifactType,
  result: GenerationResult,
  context: { audioProvider: AudioTtsProvider }
): GenerationResult => {
  switch (type) {
    case "summary":
      return requireUsableTextResult(type, result, "No usable summary content was returned.")
    case "report":
      return requireUsableTextResult(type, result, "No usable report content was returned.")
    case "compare_sources":
      return requireUsableTextResult(type, result, "No usable comparison content was returned.")
    case "timeline":
      return requireUsableTextResult(type, result, "No usable timeline content was returned.")
    case "mindmap": {
      const mermaid = typeof result.data?.mermaid === "string" ? result.data.mermaid.trim() : ""
      if (!mermaid) {
        throw new Error("No usable mind map content was returned.")
      }
      return requireUsableTextResult(type, result, "No usable mind map content was returned.")
    }
    case "data_table": {
      const table = result.data?.table
      if (!table) {
        throw new Error("No usable data table content was returned.")
      }
      return requireUsableTextResult(type, result, "No usable data table content was returned.")
    }
    case "slides":
      if (result.presentationId) return result
      return requireUsableTextResult(type, result, "No usable slide content was returned.")
    default:
      return result
  }
}
```

Update the generator helpers so they throw instead of returning failure placeholder strings:

```ts
const extractRequiredRagText = (
  response: unknown,
  label: string
): string => {
  const text =
    typeof (response as { generation?: unknown })?.generation === "string"
      ? (response as { generation: string }).generation.trim()
      : typeof (response as { answer?: unknown })?.answer === "string"
        ? (response as { answer: string }).answer.trim()
        : ""

  if (!text) {
    throw new Error(`${label} did not return usable content.`)
  }

  return text
}
```

Then call `finalizeGenerationResult(type, result, { audioProvider: audioSettings.provider })` immediately before `updateArtifactStatus(..., "completed", ...)`.

**Step 4: Run the tests to verify they pass**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx -t "summary artifacts"`

Expected: PASS for both new failure-path tests and the valid-summary control.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx
git commit -m "fix: fail workspace studio outputs on invalid rag results"
```

### Task 2: Make Quiz Download Routing Type-Aware

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`

**Step 1: Write the failing test**

Expose a dedicated `mockDownloadOutput` spy in the hoisted client mocks, then add a quiz download regression test.

```ts
it("downloads quiz artifacts locally instead of calling outputs download", async () => {
  const createObjectUrlSpy = vi
    .spyOn(URL, "createObjectURL")
    .mockReturnValue("blob:quiz")
  const revokeObjectUrlSpy = vi
    .spyOn(URL, "revokeObjectURL")
    .mockImplementation(() => {})
  const anchorClickSpy = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {})

  workspaceStoreState.generatedArtifacts = [
    {
      id: "artifact-quiz",
      type: "quiz",
      title: "Quiz",
      status: "completed",
      serverId: 42,
      content: "Question 1\nA. One\nB. Two",
      data: {
        questions: [
          { question: "Question 1", options: ["One", "Two"], answer: "One" }
        ]
      },
      createdAt: new Date("2026-02-18T10:00:00.000Z")
    }
  ]

  renderStudioPane()
  fireEvent.click(screen.getByRole("button", { name: "Download" }))

  await waitFor(() => {
    expect(createObjectUrlSpy).toHaveBeenCalled()
  })

  expect(mockDownloadOutput).not.toHaveBeenCalled()
  expect(anchorClickSpy).toHaveBeenCalled()
  expect(revokeObjectUrlSpy).toHaveBeenCalled()
})
```

**Step 2: Run the test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx -t "downloads quiz artifacts locally"`

Expected: FAIL because `handleDownloadArtifact` currently routes any artifact with `serverId` through `tldwClient.downloadOutput(...)`.

**Step 3: Write the minimal implementation**

Make download handling artifact-type aware and keep the quiz fix narrow by downloading the local artifact payload.

```ts
const downloadLocalBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const downloadTextArtifact = (
  artifact: GeneratedArtifact,
  extension: string
) => {
  const blob = new Blob([artifact.content || ""], { type: "text/plain" })
  downloadLocalBlob(blob, `${artifact.title}.${extension}`)
}

const canUseOutputsDownload = (artifact: GeneratedArtifact) =>
  artifact.type !== "quiz" &&
  artifact.type !== "flashcards" &&
  artifact.type !== "mindmap" &&
  Boolean(artifact.serverId)

const handleDownloadArtifact = async (artifact: GeneratedArtifact, format?: string) => {
  if (artifact.type === "quiz") {
    downloadTextArtifact(artifact, "txt")
    return
  }

  if (artifact.type === "audio_overview" && artifact.audioUrl) {
    ...
  }

  if (artifact.type === "slides" && artifact.presentationId) {
    ...
  }

  if (canUseOutputsDownload(artifact)) {
    ...
    return
  }

  if (artifact.content) {
    downloadTextArtifact(
      artifact,
      artifact.type === "mindmap" ? "mmd" : "txt"
    )
  }
}
```

Keep the existing text-download behavior for summary/report/timeline/compare/data-table/mindmap/flashcards. Do not introduce a new shared quiz export helper in this task.

**Step 4: Run the test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx -t "downloads quiz artifacts locally"`

Expected: PASS, with `mockDownloadOutput` untouched and local blob download behavior exercised.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx
git commit -m "fix: route workspace quiz downloads locally"
```

### Task 3: Enforce Strict Non-Browser Audio Success Semantics

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`

**Step 1: Write the failing test**

Add a test that proves a non-browser audio overview cannot complete successfully without an `audioUrl`.

```ts
it("fails non-browser audio overview generation when TTS does not return audio", async () => {
  workspaceStoreState.audioSettings = {
    ...baseAudioSettings,
    provider: "tldw",
    model: "kokoro"
  }
  mockRagSearch.mockResolvedValue({ generation: "Audio script" })
  mockSynthesizeSpeech.mockRejectedValue(new Error("TTS service unavailable"))

  renderStudioPane()
  fireEvent.click(screen.getByRole("button", { name: "Audio Summary" }))

  await waitFor(() => {
    expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
      "artifact-1",
      "failed",
      expect.objectContaining({
        errorMessage: expect.stringContaining("audio")
      })
    )
  })

  expect(mockMessageSuccess).not.toHaveBeenCalled()
})
```

**Step 2: Run the test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx -t "fails non-browser audio overview generation"`

Expected: FAIL because `generateAudioOverview` currently catches non-abort TTS errors and returns script text as a successful result.

**Step 3: Write the minimal implementation**

Remove the script-only success fallback for non-browser providers and let TTS failure propagate into the shared failed-artifact path.

```ts
async function generateAudioOverview(
  mediaIds: number[],
  audioSettings: AudioGenerationSettings,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  const script = extractRequiredRagText(
    await tldwClient.ragSearch(...),
    "Audio overview"
  )

  if (audioSettings.provider === "browser") {
    return {
      content: script,
      audioFormat: "browser",
      ...usage
    }
  }

  const audioBuffer = await tldwClient.synthesizeSpeech(script, {
    model: audioSettings.model,
    voice: audioSettings.voice,
    responseFormat: audioSettings.format,
    speed: audioSettings.speed,
    signal: abortSignal
  })

  const audioBlob = new Blob([audioBuffer], {
    type: mimeTypes[audioSettings.format] || "audio/mpeg"
  })

  return {
    content: script,
    audioUrl: URL.createObjectURL(audioBlob),
    audioFormat: audioSettings.format,
    ...usage
  }
}
```

In `finalizeGenerationResult`, explicitly reject non-browser audio results that do not include `audioUrl`.

**Step 4: Run the test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx -t "fails non-browser audio overview generation"`

Expected: PASS, with the artifact finalized as failed and no success toast.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx
git commit -m "fix: require real audio artifacts in workspace studio"
```

### Verification Checklist

- Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`
- Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
- Run: `git diff --stat`
- Confirm only the planned files changed:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`

### Verification Results

- PASS: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`
- PASS: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
- PASS WITH LIMITATION: `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx -f json -o /private/tmp/bandit_workspace_playground_studio_output_failure.json`
- Note: Bandit reported zero findings but also AST parse errors because the touched files are TypeScript, not Python.
