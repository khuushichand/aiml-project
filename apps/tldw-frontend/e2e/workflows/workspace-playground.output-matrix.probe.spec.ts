import { readFileSync, statSync } from "node:fs"
import path from "node:path"

import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../utils/fixtures"
import {
  TEST_CONFIG,
  fetchWithApiKey,
  generateTestId,
  seedAuth,
} from "../utils/helpers"
import { WorkspacePlaygroundPage } from "../utils/page-objects"

const DESKTOP_VIEWPORT = { width: 1440, height: 900 }

type WorkspaceProbeOutput = {
  label: string
  textDownload: boolean
}

const BACKEND_SUPPORTED_OUTPUTS: WorkspaceProbeOutput[] = [
  { label: "Report", textDownload: true },
  { label: "Compare Sources", textDownload: true },
  { label: "Timeline", textDownload: true },
]

const hasErrorText = (content: string) =>
  /error encountered|generation failed|generation canceled before completion|interrupted|no usable|download failed|could not/i.test(
    content,
  )
const WORKSPACE_EMBEDDING_PROVIDER = "huggingface"
const WORKSPACE_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

type WorkspaceProbeSource = {
  mediaId: number
  title: string
  type: "pdf" | "video" | "audio" | "website" | "document" | "text"
  url?: string
}

const setWorkspaceSelectedModel = async (
  page: Parameters<typeof seedAuth>[0],
  modelId: string,
): Promise<void> => {
  await page.evaluate((nextModel) => {
    const store = (window as { __tldw_useStoreMessageOption?: unknown })
      .__tldw_useStoreMessageOption as
        | {
            setState?: (nextState: Record<string, unknown>) => void
          }
        | undefined
    if (!store?.setState) {
      throw new Error("Message option store is unavailable on window")
    }
    store.setState({ selectedModel: nextModel })
  }, modelId)
}

const fetchWithApiKeyTimeout = async (
  url: string,
  init: RequestInit,
  timeoutMs = 5_000,
): Promise<Response | null> => {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    return await fetchWithApiKey(url, TEST_CONFIG.apiKey, {
      ...init,
      signal: controller.signal,
    })
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

const cleanupMediaItem = async (mediaId: number | null): Promise<void> => {
  if (!Number.isFinite(mediaId) || (mediaId as number) <= 0) {
    return
  }

  const targetId = Math.trunc(mediaId as number)
  const trashResponse = await fetchWithApiKeyTimeout(
    `${TEST_CONFIG.serverUrl}/api/v1/media/${targetId}`,
    { method: "DELETE" },
  )

  if (
    trashResponse &&
    !trashResponse.ok &&
    trashResponse.status !== 204 &&
    trashResponse.status !== 404
  ) {
    throw new Error(
      `Soft delete for media ${targetId} returned HTTP ${trashResponse.status}`,
    )
  }

  const permanentResponse = await fetchWithApiKeyTimeout(
    `${TEST_CONFIG.serverUrl}/api/v1/media/${targetId}/permanent`,
    { method: "DELETE" },
  )

  if (
    permanentResponse &&
    !permanentResponse.ok &&
    permanentResponse.status !== 204 &&
    permanentResponse.status !== 404
  ) {
    throw new Error(
      `Permanent delete for media ${targetId} returned HTTP ${permanentResponse.status}`,
    )
  }
}

const fetchLiveMediaDetail = async (
  mediaId: number,
): Promise<Record<string, unknown>> => {
  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/media/${mediaId}?include_content=true&include_versions=false&include_version_content=false`,
  )
  if (!response.ok) {
    throw new Error(`GET /api/v1/media/${mediaId} returned HTTP ${response.status}`)
  }
  const payload = await response.json().catch(() => null)
  if (!payload || typeof payload !== "object") {
    throw new Error(`GET /api/v1/media/${mediaId} returned a non-object payload`)
  }
  return payload as Record<string, unknown>
}

const createLiveWorkspaceProbeSource = async (
  title: string,
  content: string,
): Promise<WorkspaceProbeSource> => {
  const body = new FormData()
  body.append("media_type", "document")
  body.append("title", title)
  body.append("generate_embeddings", "true")
  body.append("embedding_dispatch_mode", "background")
  body.append("embedding_provider", WORKSPACE_EMBEDDING_PROVIDER)
  body.append("embedding_model", WORKSPACE_EMBEDDING_MODEL)
  body.append("perform_analysis", "false")
  body.append("perform_chunking", "true")
  body.append("overwrite", "false")
  body.append("chunk_method", "words")
  body.append("chunk_size", "128")
  body.append("chunk_overlap", "16")
  body.append(
    "files",
    new Blob([content], { type: "text/plain" }),
    `${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.txt`,
  )

  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/media/add`,
    TEST_CONFIG.apiKey,
    {
      method: "POST",
      body,
    },
  )
  if (!response.ok) {
    throw new Error(
      `Failed to create workspace output probe media: HTTP ${response.status}`,
    )
  }

  const payload = (await response.json().catch(() => null)) as Record<string, unknown> | null
  const createdCandidate =
    payload?.results?.[0]?.media_id ??
    payload?.results?.[0]?.db_id ??
    payload?.result?.media_id ??
    payload?.result?.db_id ??
    payload?.media_id ??
    payload?.db_id ??
    payload?.id
  const mediaId = Number(createdCandidate)
  if (!Number.isFinite(mediaId) || mediaId <= 0) {
    throw new Error(
      `Workspace output probe media add returned no media id: ${JSON.stringify(payload)}`,
    )
  }

  const uploadResult = payload?.results?.[0] ?? payload?.result ?? payload
  expect(
    uploadResult?.embeddings_scheduled,
    `Expected workspace output probe media to schedule embeddings, received ${JSON.stringify(
      payload,
    )}`,
  ).toBeTruthy()

  let liveMediaDetail = await fetchLiveMediaDetail(mediaId)
  await expect
    .poll(
      async () => {
        liveMediaDetail = await fetchLiveMediaDetail(mediaId)
        return (
          (liveMediaDetail.processing as Record<string, unknown> | undefined)
            ?.vector_processing_status ?? null
        )
      },
      {
        timeout: 60_000,
        message: `Timed out waiting for workspace output probe embeddings: ${JSON.stringify(
          liveMediaDetail,
        )}`,
      },
    )
    .toBe(1)

  return {
    mediaId,
    title,
    type: "document",
    url: `https://example.com/workspace-output-probe/${mediaId}`,
  }
}

const buildLiveProbeDocuments = (
  uniqueSlug: string,
): Array<{ title: string; content: string }> => {
  const upperSlug = uniqueSlug.toUpperCase()
  return [
    {
      title: `Workspace Output Briefing Alpha ${uniqueSlug}`,
      content: [
        `Program Alpha briefing ${upperSlug} covers a cross-functional migration effort.`,
        "In March 2023 the team audited 48 legacy workflows and found slow manual review as the main blocker.",
        "In June 2023 the team launched an evidence review board with members from research, security, and operations.",
        "In September 2023 the project introduced source-grounded summaries, weekly checkpoints, and incident rehearsal drills.",
        "The briefing groups work into four themes: governance, evidence quality, delivery cadence, and operator training.",
        "Governance requires a review board, named owners, and written escalation paths.",
        "Evidence quality requires citations, contradiction checks, and freshness reviews every Friday.",
        "Delivery cadence requires a published roadmap with milestones in October 2023, January 2024, and April 2024.",
        "Operator training requires scenario drills, postmortems, and a searchable lessons-learned log.",
      ].join("\n"),
    },
    {
      title: `Workspace Output Briefing Beta ${uniqueSlug}`,
      content: [
        `Program Beta briefing ${upperSlug} documents how a second team responded to the same migration program.`,
        "In April 2023 the Beta team prioritized privacy review, source permissions, and data retention policy updates.",
        "In July 2023 the team published a comparative scorecard for analyst speed, answer trust, and source coverage.",
        "In November 2023 the team adopted a staged rollout with pilot, beta, and general availability checkpoints.",
        "The briefing compares three recommendations: tighten privacy defaults, expand source coverage, and shorten analyst feedback loops.",
        "Privacy defaults include shorter retention windows, explicit source labels, and reviewer approval before sharing.",
        "Source coverage includes PDF manuals, HTML policy pages, and internal meeting notes tagged by topic.",
        "Feedback loops include weekly office hours, a bug queue triage every Tuesday, and monthly readiness reviews.",
        "The concluding recommendation is to align governance, privacy, and evidence review so rollout decisions stay explainable.",
      ].join("\n"),
    },
  ]
}

const setupLiveProbeWorkspace = async (args: {
  authedPage: Parameters<typeof seedAuth>[0]
  workspacePage: WorkspacePlaygroundPage
  availableModel: string
  uniqueSlug: string
  documentCount: number
}): Promise<number[]> => {
  const { authedPage, workspacePage, availableModel, uniqueSlug, documentCount } = args
  const createdMediaIds: number[] = []

  await workspacePage.goto()
  await workspacePage.waitForReady()
  await setWorkspaceSelectedModel(authedPage, availableModel)

  const liveSources: WorkspaceProbeSource[] = []
  for (const document of buildLiveProbeDocuments(uniqueSlug).slice(0, documentCount)) {
    const source = await createLiveWorkspaceProbeSource(document.title, document.content)
    createdMediaIds.push(source.mediaId)
    liveSources.push(source)
  }

  await workspacePage.seedSources(liveSources)
  await expect
    .poll(async () => (await workspacePage.getSourceIds()).length, {
      timeout: 10_000,
    })
    .toBeGreaterThanOrEqual(documentCount)

  const sourceIds = await workspacePage.getSourceIds()
  for (const sourceId of sourceIds.slice(0, documentCount)) {
    await workspacePage.selectSourceById(sourceId)
    await workspacePage.expectSourceSelected(sourceId)
  }

  return createdMediaIds
}

const verifyGeneratedOutputs = async (
  authedPage: Parameters<typeof seedAuth>[0],
  outputs: WorkspaceProbeOutput[],
): Promise<void> => {
  const cards = authedPage.locator("[data-testid^='studio-artifact-card-']")

  for (const output of outputs) {
    const beforeCount = await cards.count()
    await authedPage.getByRole("button", { name: output.label, exact: true }).click()

    await expect(cards).toHaveCount(beforeCount + 1, { timeout: 90_000 })
    const artifactCard = cards.first()
    await expect(artifactCard).toBeVisible({ timeout: 30_000 })

    await expect
      .poll(
        async () => {
          const downloadVisible = await artifactCard
            .getByRole("button", { name: "Download" })
            .isVisible()
            .catch(() => false)
          if (downloadVisible) {
            return "completed"
          }

          const cardText = (await artifactCard.textContent()) || ""
          if (
            /failed|encountered an error|generation canceled before completion|interrupted|no usable/i.test(
              cardText,
            )
          ) {
            return `failed:${cardText}`
          }

          return "pending"
        },
        {
          timeout: 120_000,
          message: `${output.label} did not reach a completed state`,
        },
      )
      .toBe("completed")

    await expect(artifactCard).not.toContainText(/failed|encountered an error/i, {
      timeout: 5_000,
    })

    const downloadButton = artifactCard.getByRole("button", { name: "Download" })
    await expect(downloadButton).toBeVisible({ timeout: 30_000 })

    if (output.label === "Slides") {
      await downloadButton.click()
      const markdownOption = authedPage
        .getByRole("button", { name: /Markdown/i })
        .last()
      await expect(markdownOption).toBeVisible({ timeout: 10_000 })
      const download = await Promise.all([
        authedPage.waitForEvent("download", { timeout: 30_000 }),
        markdownOption.click(),
      ]).then(([event]) => event)
      const artifactPath = path.join(
        process.cwd(),
        "test-results",
        download.suggestedFilename(),
      )
      await download.saveAs(artifactPath)
      const content = readFileSync(artifactPath, "utf8")
      expect(content.trim().length).toBeGreaterThan(20)
      expect(hasErrorText(content)).toBe(false)
      continue
    }

    const download = await Promise.all([
      authedPage.waitForEvent("download", { timeout: 30_000 }),
      downloadButton.click(),
    ]).then(([event]) => event)

    const artifactPath = path.join(
      process.cwd(),
      "test-results",
      download.suggestedFilename(),
    )
    await download.saveAs(artifactPath)

    if (output.textDownload) {
      const content = readFileSync(artifactPath, "utf8")
      expect(content.trim().length).toBeGreaterThan(20)
      expect(hasErrorText(content)).toBe(false)
    } else {
      expect(statSync(artifactPath).size).toBeGreaterThan(32)
    }
  }
}

test.describe("Workspace Playground output matrix probe", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await page.setViewportSize(DESKTOP_VIEWPORT)
  })

  test("generates and downloads live backend-supported research outputs", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    test.setTimeout(420_000)
    skipIfServerUnavailable(serverInfo)
    const availableModel = serverInfo.models?.[0]
    test.skip(
      !availableModel,
      "Skipping workspace output matrix probe: no live chat models reported by /api/v1/llm/providers",
    )

    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    const uniqueSlug = generateTestId("workspace-output-probe")
    let createdMediaIds: number[] = []

    try {
      createdMediaIds = await setupLiveProbeWorkspace({
        authedPage,
        workspacePage,
        availableModel: availableModel!,
        uniqueSlug,
        documentCount: 2,
      })
      await verifyGeneratedOutputs(authedPage, BACKEND_SUPPORTED_OUTPUTS)
      await assertNoCriticalErrors(diagnostics)
    } finally {
      for (const mediaId of createdMediaIds) {
        await cleanupMediaItem(mediaId)
      }
    }
  })

  test("generates and downloads live slides for a document-backed workspace source", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    test.setTimeout(300_000)
    skipIfServerUnavailable(serverInfo)
    const availableModel = serverInfo.models?.[0]
    test.skip(
      !availableModel,
      "Skipping workspace slides probe: no live chat models reported by /api/v1/llm/providers",
    )

    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    const uniqueSlug = generateTestId("workspace-slides-probe")
    let createdMediaIds: number[] = []

    try {
      createdMediaIds = await setupLiveProbeWorkspace({
        authedPage,
        workspacePage,
        availableModel: availableModel!,
        uniqueSlug,
        documentCount: 1,
      })
      await verifyGeneratedOutputs(authedPage, [
        { label: "Slides", textDownload: true },
      ])
      await assertNoCriticalErrors(diagnostics)
    } finally {
      for (const mediaId of createdMediaIds) {
        await cleanupMediaItem(mediaId)
      }
    }
  })
})
