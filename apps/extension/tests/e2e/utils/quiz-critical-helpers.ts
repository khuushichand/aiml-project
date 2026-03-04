import {
  expect,
  test,
  type BrowserContext,
  type Page,
  type Response as PlaywrightResponse,
  type TestInfo
} from "@playwright/test"
import path from "path"
import { grantHostPermission } from "./permissions"
import { requireRealServerConfig, launchWithExtensionOrSkip } from "./real-server"

type QuestionSeed = {
  question_type: "multiple_choice" | "true_false" | "fill_blank"
  question_text: string
  options?: string[]
  correct_answer: number | string
  points: number
  order_index: number
}

type QuizSeedFixture = {
  quizIds: number[]
  mainQuizId: number
  mainQuizName: string
  baseQuestions: QuestionSeed[]
}

type QuizApiResponse = {
  id: number
  name: string
  description?: string | null
  time_limit_seconds?: number | null
  passing_score?: number | null
  version: number
}

type QuestionApiResponse = {
  id: number
  question_text: string
  correct_answer: number | string
}

type ListResponse<T> = {
  items: T[]
  count: number
}

type RequestErrorEntry = {
  method?: string
  path?: string
  status?: number
  error?: string
  source?: string
  at?: string
}

const UNSAVED_CREATE_PROMPT = /You have unsaved quiz changes\. Leave Create tab\?/i

const waitFor = async (ms: number) => {
  await new Promise((resolve) => setTimeout(resolve, ms))
}

const normalizeServerUrl = (serverUrl: string) =>
  serverUrl.match(/^https?:\/\//) ? serverUrl : `http://${serverUrl}`

const apiRequest = async <T>(
  baseUrl: string,
  apiKey: string,
  route: string,
  init: RequestInit = {}
): Promise<T> => {
  const normalizedBase = baseUrl.replace(/\/$/, "")
  const baseHeaders: Record<string, string> = {
    "x-api-key": apiKey
  }

  const requestHeaders: Record<string, string> = {
    ...baseHeaders,
    ...((init.headers as Record<string, string> | undefined) ?? {})
  }

  const res = await fetch(`${normalizedBase}${route}`, {
    ...init,
    headers: requestHeaders
  })

  const text = await res.text()
  let payload: unknown = null
  if (text.length > 0) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!res.ok) {
    throw new Error(
      `API ${init.method ?? "GET"} ${route} failed: ${res.status} ${res.statusText} ${text}`
    )
  }

  return payload as T
}

const seedQuizFixture = async (
  baseUrl: string,
  apiKey: string,
  baseName: string,
  quizCount = 3
): Promise<QuizSeedFixture> => {
  const mainQuizName = `${baseName} Main`

  const baseQuestions: QuestionSeed[] = [
    {
      question_type: "multiple_choice",
      question_text: `${baseName} Q1: 2 + 2 = ?`,
      options: ["4", "3", "2", "1"],
      correct_answer: 0,
      points: 1,
      order_index: 0
    },
    {
      question_type: "true_false",
      question_text: `${baseName} Q2: The sky is blue.`,
      correct_answer: "true",
      points: 1,
      order_index: 1
    },
    {
      question_type: "fill_blank",
      question_text: `${baseName} Q3: Capital of Japan`,
      correct_answer: "Tokyo",
      points: 1,
      order_index: 2
    },
    {
      question_type: "multiple_choice",
      question_text: `${baseName} Q4: Primary color in RGB`,
      options: ["Red", "Green", "Blue", "Yellow"],
      correct_answer: 0,
      points: 1,
      order_index: 3
    },
    {
      question_type: "true_false",
      question_text: `${baseName} Q5: 5 is even.`,
      correct_answer: "false",
      points: 1,
      order_index: 4
    },
    {
      question_type: "fill_blank",
      question_text: `${baseName} Q6: H2O is ___`,
      correct_answer: "water",
      points: 1,
      order_index: 5
    }
  ]

  const createdQuizzes: QuizApiResponse[] = []

  for (let i = 0; i < quizCount; i += 1) {
    const created = await apiRequest<QuizApiResponse>(baseUrl, apiKey, "/api/v1/quizzes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: i === 0 ? mainQuizName : `${baseName} Extra ${i}`,
        description: "Created by Playwright"
      })
    })
    createdQuizzes.push(created)
  }

  const mainQuiz = createdQuizzes[0]
  for (const question of baseQuestions) {
    await apiRequest<QuestionApiResponse>(
      baseUrl,
      apiKey,
      `/api/v1/quizzes/${mainQuiz.id}/questions`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_type: question.question_type,
          question_text: question.question_text,
          options: question.options ?? null,
          correct_answer: question.correct_answer,
          points: question.points,
          order_index: question.order_index
        })
      }
    )
  }

  return {
    quizIds: createdQuizzes.map((quiz) => quiz.id),
    mainQuizId: mainQuiz.id,
    mainQuizName,
    baseQuestions
  }
}

const cleanupQuizzes = async (baseUrl: string, apiKey: string, quizIds: number[]) => {
  for (const quizId of quizIds) {
    try {
      const quiz = await apiRequest<QuizApiResponse>(baseUrl, apiKey, `/api/v1/quizzes/${quizId}`)
      await apiRequest<void>(
        baseUrl,
        apiKey,
        `/api/v1/quizzes/${quizId}?expected_version=${quiz.version}`,
        {
          method: "DELETE"
        }
      )
    } catch (error) {
      // Keep cleanup best effort to avoid masking the primary assertion failures.
      console.warn(`[quiz-critical] cleanup failed for quiz ${quizId}:`, error)
    }
  }
}

const getLastRequestError = async (page: Page): Promise<RequestErrorEntry | null> => {
  return await page.evaluate(async () => {
    const normalizePayload = (payload: unknown): RequestErrorEntry | null => {
      if (!payload) return null
      if (typeof payload === "string") {
        try {
          const parsed = JSON.parse(payload)
          if (parsed && typeof parsed === "object") {
            return parsed as RequestErrorEntry
          }
        } catch {
          return { error: payload }
        }
      }
      if (payload && typeof payload === "object") {
        return payload as RequestErrorEntry
      }
      return null
    }

    const readFromStorage = (storage: { get: (...args: any[]) => void } | null) =>
      new Promise<RequestErrorEntry | null>((resolve) => {
        if (!storage?.get) {
          resolve(null)
          return
        }
        try {
          storage.get("__tldwLastRequestError", (result: Record<string, unknown> | undefined) => {
            const payload = result?.__tldwLastRequestError
            resolve(normalizePayload(payload))
          })
        } catch {
          resolve(null)
        }
      })

    const chromeStorage = (globalThis as { chrome?: { storage?: { local?: { get: (...args: any[]) => void } } } })
      .chrome?.storage?.local
    const browserStorage = (globalThis as { browser?: { storage?: { local?: { get: (...args: any[]) => void } } } })
      .browser?.storage?.local

    const chromeResult = await readFromStorage(chromeStorage ?? null)
    if (chromeResult) return chromeResult
    return await readFromStorage(browserStorage ?? null)
  })
}

const getRecentRequestErrors = async (page: Page): Promise<RequestErrorEntry[]> => {
  return await page.evaluate(async () => {
    const normalizePayload = (payload: unknown): RequestErrorEntry | null => {
      if (!payload) return null
      if (typeof payload === "string") {
        try {
          const parsed = JSON.parse(payload)
          if (parsed && typeof parsed === "object") {
            return parsed as RequestErrorEntry
          }
        } catch {
          return { error: payload }
        }
      }
      if (payload && typeof payload === "object") {
        return payload as RequestErrorEntry
      }
      return null
    }

    const readFromStorage = (storage: { get: (...args: any[]) => void } | null) =>
      new Promise<RequestErrorEntry[]>((resolve) => {
        if (!storage?.get) {
          resolve([])
          return
        }
        try {
          storage.get("__tldwRequestErrors", (result: Record<string, unknown> | undefined) => {
            const payload = result?.__tldwRequestErrors
            if (!Array.isArray(payload)) {
              resolve([])
              return
            }
            const normalized = payload
              .map((entry) => normalizePayload(entry))
              .filter((entry): entry is RequestErrorEntry => entry != null)
            resolve(normalized)
          })
        } catch {
          resolve([])
        }
      })

    const chromeStorage = (globalThis as { chrome?: { storage?: { local?: { get: (...args: any[]) => void } } } })
      .chrome?.storage?.local
    const browserStorage = (globalThis as { browser?: { storage?: { local?: { get: (...args: any[]) => void } } } })
      .browser?.storage?.local

    const chromeResult = await readFromStorage(chromeStorage ?? null)
    if (chromeResult.length > 0) return chromeResult
    return await readFromStorage(browserStorage ?? null)
  })
}

const enableDirectRequestFallback = async (page: Page): Promise<boolean> => {
  return await page.evaluate(() => {
    const patchRuntimeSendMessage = (runtime: any): boolean => {
      if (!runtime || typeof runtime.sendMessage !== "function") return false
      if (runtime.__tldwE2EDirectFallbackEnabled) return true

      const originalSendMessage = runtime.sendMessage.bind(runtime)
      const wrappedSendMessage = (...args: any[]) => {
        const message = args[0]
        if (message && typeof message === "object" && message.type === "tldw:request") {
          throw new Error("Could not establish connection. Receiving end does not exist.")
        }
        return originalSendMessage(...args)
      }

      try {
        runtime.sendMessage = wrappedSendMessage
      } catch {
        try {
          Object.defineProperty(runtime, "sendMessage", {
            value: wrappedSendMessage,
            configurable: true
          })
        } catch {
          return false
        }
      }

      runtime.__tldwE2EDirectFallbackEnabled = true
      return true
    }

    const browserRuntime = (globalThis as { browser?: { runtime?: unknown } }).browser?.runtime
    const chromeRuntime = (globalThis as { chrome?: { runtime?: unknown } }).chrome?.runtime
    return patchRuntimeSendMessage(browserRuntime) || patchRuntimeSendMessage(chromeRuntime)
  })
}

const waitForQuizIdByName = async (
  baseUrl: string,
  apiKey: string,
  quizName: string
): Promise<number | null> => {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const list = await apiRequest<ListResponse<QuizApiResponse>>(
      baseUrl,
      apiKey,
      `/api/v1/quizzes?q=${encodeURIComponent(quizName)}&limit=10&offset=0`
    )
    const exactMatch = list.items.find((item) => item.name === quizName)
    if (typeof exactMatch?.id === "number") {
      return exactMatch.id
    }
    await waitFor(300)
  }

  return null
}

const openQuizWorkspace = async (page: Page, optionsUrl: string) => {
  await page.goto(`${optionsUrl}#/quiz`, { waitUntil: "domcontentloaded" })
  await expect(page.getByRole("tab", { name: /Manage/i })).toBeVisible({ timeout: 20000 })
}

const assertPreflightOrSkip = async (serverUrl: string, apiKey: string) => {
  let preflight: Response | null = null
  try {
    preflight = await fetch(`${serverUrl}/api/v1/quizzes?limit=1&offset=0`, {
      headers: { "x-api-key": apiKey }
    })
  } catch (error) {
    test.skip(true, `Quiz API preflight unreachable in this environment: ${String(error)}`)
    return
  }

  if (!preflight.ok) {
    const body = await preflight.text().catch(() => "")
    test.skip(
      true,
      `Quiz API preflight failed: ${preflight.status} ${preflight.statusText} ${body}`
    )
  }
}

const setupQuizWorkspace = async () => {
  const { serverUrl, apiKey } = requireRealServerConfig(test)
  const normalizedServerUrl = normalizeServerUrl(serverUrl)

  await assertPreflightOrSkip(normalizedServerUrl, apiKey)

  const extPath = path.resolve("build/chrome-mv3")
  const launchResult = await launchWithExtensionOrSkip(test, extPath, {
    seedConfig: {
      tldwConfig: {
        serverUrl: normalizedServerUrl,
        authMode: "single-user",
        apiKey
      }
    }
  })

  const context = launchResult.context
  const { page, extensionId, optionsUrl } = launchResult
  const origin = new URL(normalizedServerUrl).origin + "/*"
  const granted = await grantHostPermission(context, extensionId, origin)
  if (!granted) {
    test.skip(
      true,
      "Host permission not granted for tldw_server origin; allow it in chrome://extensions > tldw Assistant > Site access, then re-run"
    )
  }

  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent("tldw:check-connection"))
  })
  await enableDirectRequestFallback(page)

  return {
    context,
    page,
    optionsUrl,
    apiKey,
    normalizedServerUrl
  }
}

const findTakeQuizCard = async (page: Page, quizId: number) => {
  let card = page.getByTestId(`take-quiz-card-${quizId}`)
  if ((await card.count()) > 0) {
    return card.first()
  }

  const pagination = page.locator(".ant-pagination").first()
  const nextButton = pagination.locator(".ant-pagination-next")
  for (let pageIndex = 0; pageIndex < 8; pageIndex += 1) {
    if ((await nextButton.count()) === 0) break
    if ((await nextButton.first().getAttribute("aria-disabled")) === "true") break
    const hasDisabledClass = await nextButton.first().evaluate((el) =>
      el.classList.contains("ant-pagination-disabled")
    )
    if (hasDisabledClass) break
    await nextButton.first().click()
    await waitFor(300)
    card = page.getByTestId(`take-quiz-card-${quizId}`)
    if ((await card.count()) > 0) {
      return card.first()
    }
  }

  return null
}

export const runStrictEditQuizMetadataAndQuestionSet = async () => {
  let context: BrowserContext | null = null
  const quizIds: number[] = []

  try {
    const workspace = await setupQuizWorkspace()
    context = workspace.context

    const unique = Date.now()
    const baseName = `E2E Quiz ${unique}`
    const fixture = await seedQuizFixture(
      workspace.normalizedServerUrl,
      workspace.apiKey,
      baseName,
      4
    )
    quizIds.push(...fixture.quizIds)

    const updatedQuizName = `${fixture.mainQuizName} Updated`
    const updatedDescription = "Updated by Playwright"

    const { page } = workspace
    await openQuizWorkspace(page, workspace.optionsUrl)

    await page.getByRole("tab", { name: /Manage/i }).click()
    const managePanel = page
      .getByRole("tabpanel")
      .filter({ has: page.getByPlaceholder(/Search quizzes/i) })
    const searchInput = managePanel.getByPlaceholder(/Search quizzes/i)
    await searchInput.fill(baseName)

    const editButton = managePanel.getByTestId(`quiz-edit-${fixture.mainQuizId}`)
    await expect(editButton).toBeVisible({ timeout: 20000 })
    await editButton.click({ force: true })

    const editDialog = page.getByTestId("manage-edit-quiz-modal")
    await expect(editDialog).toBeVisible({ timeout: 20000 })

    await editDialog.getByLabel(/Quiz Name/i).fill(updatedQuizName)
    await editDialog.getByLabel(/Description/i).fill(updatedDescription)
    await editDialog.getByLabel(/Time Limit/i).fill("15")
    await editDialog.getByLabel(/Passing Score/i).fill("70")

    await expect(editDialog.getByText(fixture.baseQuestions[0].question_text)).toBeVisible()

    const updateResponses: Array<{
      method: string
      path: string
      status: number
      body: string
    }> = []
    const responseListener = async (response: PlaywrightResponse) => {
      const method = response.request().method().toUpperCase()
      if (method !== "PUT" && method !== "PATCH") return
      try {
        const parsed = new URL(response.url())
        if (!/^\/api\/v1\/quizzes\/\d+$/.test(parsed.pathname)) return
        const body = await response
          .text()
          .then((text) => text.slice(0, 250))
          .catch(() => "")
        updateResponses.push({
          method,
          path: `${parsed.pathname}${parsed.search}`,
          status: response.status(),
          body
        })
      } catch {
        // Ignore malformed URLs in response listeners.
      }
    }
    page.on("response", responseListener)

    const editSaveButton = editDialog.getByRole("button", { name: /^Save$/i })
    await expect(editSaveButton).toHaveCount(1)
    let persistedQuiz: QuizApiResponse | null = null
    let lastCandidateQuiz: QuizApiResponse | null = null
    let lastPollError: string | null = null
    let sawUpdateErrorToast = false
    saveLoop: for (let saveAttempt = 0; saveAttempt < 3; saveAttempt += 1) {
      await expect(editSaveButton).toBeEnabled()
      await editSaveButton.scrollIntoViewIfNeeded()
      await editSaveButton.click()

      for (let pollAttempt = 0; pollAttempt < 20; pollAttempt += 1) {
        try {
          const candidate = await apiRequest<QuizApiResponse>(
            workspace.normalizedServerUrl,
            workspace.apiKey,
            `/api/v1/quizzes/${fixture.mainQuizId}`
          )
          lastCandidateQuiz = candidate
          const isExpected =
            candidate.name === updatedQuizName &&
            (candidate.description ?? "").includes("Updated by Playwright") &&
            candidate.passing_score === 70 &&
            candidate.time_limit_seconds === 900
          if (isExpected) {
            persistedQuiz = candidate
            break saveLoop
          }
        } catch (error) {
          lastPollError = String(error)
        }
        await waitFor(500)
      }

      const updateErrorToast = page.getByText(/Failed to update quiz/i).last()
      const hasImmediateUpdateErrorToast = await updateErrorToast
        .isVisible({ timeout: 1200 })
        .catch(() => false)
      if (hasImmediateUpdateErrorToast) {
        sawUpdateErrorToast = true
      }

      const dialogStillVisible = await editDialog.isVisible().catch(() => false)
      if (!dialogStillVisible) {
        break
      }
    }
    page.off("response", responseListener)

    const updateErrorToast = page.getByText(/Failed to update quiz/i).last()
    const hasUpdateErrorToast = await updateErrorToast
      .isVisible({ timeout: 1500 })
      .catch(() => false)
    const hasAnyUpdateErrorToast = sawUpdateErrorToast || hasUpdateErrorToast
    const editRequestError = await getLastRequestError(page)
    const recentRequestErrors = await getRecentRequestErrors(page)
    const relevantEditRequestError =
      editRequestError?.path?.includes(`/api/v1/quizzes/${fixture.mainQuizId}`) ? editRequestError : null
    const relevantRecentRequestErrors = recentRequestErrors.filter((entry) => {
      const path = entry.path ?? ""
      const method = (entry.method ?? "").toUpperCase()
      return (
        path.includes(`/api/v1/quizzes/${fixture.mainQuizId}`) ||
        (/^\/api\/v1\/quizzes(?:\/\d+)?/.test(path) &&
          (method === "POST" || method === "PATCH" || method === "PUT"))
      )
    })
    const updateResponsesSummary =
      updateResponses.length > 0
        ? ` [updateResponses=${updateResponses
            .map(
              (entry) =>
                `${entry.method} ${entry.path} -> ${entry.status}${entry.body ? ` ${entry.body}` : ""}`
            )
            .join(" || ")}]`
        : " [updateResponses=none]"
    const recentRequestErrorsSummary =
      relevantRecentRequestErrors.length > 0
        ? ` [recentRequestErrors=${relevantRecentRequestErrors
            .map(
              (entry) =>
                `${entry.method ?? "?"} ${entry.path ?? "?"} -> ${entry.status ?? "?"} ${entry.error ?? "?"}`
            )
            .join(" || ")}]`
        : " [recentRequestErrors=none]"
    const lastCandidateSummary = lastCandidateQuiz
      ? ` [lastQuizState name=${lastCandidateQuiz.name} description=${lastCandidateQuiz.description ?? "null"} passing=${String(lastCandidateQuiz.passing_score)} timeLimit=${String(lastCandidateQuiz.time_limit_seconds)} version=${lastCandidateQuiz.version}]`
      : ""
    const lastPollErrorSummary = lastPollError ? ` [lastPollError=${lastPollError}]` : ""
    const editErrorSummary = relevantEditRequestError
      ? ` [lastRequestError method=${relevantEditRequestError.method ?? "?"} path=${relevantEditRequestError.path ?? "?"} status=${relevantEditRequestError.status ?? "?"} error=${relevantEditRequestError.error ?? "?"}]${updateResponsesSummary}${recentRequestErrorsSummary}${lastCandidateSummary}${lastPollErrorSummary}`
      : hasAnyUpdateErrorToast
        ? ` [uiToast=Failed to update quiz]${updateResponsesSummary}${recentRequestErrorsSummary}${lastCandidateSummary}${lastPollErrorSummary}`
        : `${updateResponsesSummary}${recentRequestErrorsSummary}${lastCandidateSummary}${lastPollErrorSummary}`
    expect(
      persistedQuiz,
      `Quiz metadata update was not observed via API polling.${editErrorSummary}`
    ).not.toBeNull()
    if (persistedQuiz == null) {
      throw new Error(`Quiz metadata update was not observed via API polling.${editErrorSummary}`)
    }

    if (await editDialog.isVisible().catch(() => false)) {
      const cancelButton = editDialog.getByRole("button", { name: /^Cancel$/i })
      if ((await cancelButton.count()) > 0) {
        await cancelButton.click({ force: true })
      } else {
        await page.keyboard.press("Escape")
      }
      await expect(editDialog).toBeHidden({ timeout: 10000 })
    }

    await searchInput.fill(updatedQuizName)
    await expect(managePanel.getByText(updatedQuizName, { exact: true })).toBeVisible({
      timeout: 10000
    })

    expect(persistedQuiz.name).toBe(updatedQuizName)
    expect(persistedQuiz.description ?? "").toContain("Updated by Playwright")
    expect(persistedQuiz.passing_score).toBe(70)
    expect(persistedQuiz.time_limit_seconds).toBe(900)

    const persistedQuestions = await apiRequest<ListResponse<QuestionApiResponse>>(
      workspace.normalizedServerUrl,
      workspace.apiKey,
      `/api/v1/quizzes/${fixture.mainQuizId}/questions?include_answers=true&limit=200&offset=0`
    )
    expect(persistedQuestions.items.length).toBeGreaterThan(0)
    expect(
      persistedQuestions.items.some((item) => item.question_text === fixture.baseQuestions[0].question_text)
    ).toBeTruthy()
  } finally {
    if (quizIds.length > 0) {
      const { serverUrl, apiKey } = requireRealServerConfig(test)
      await cleanupQuizzes(normalizeServerUrl(serverUrl), apiKey, quizIds)
    }
    await context?.close()
  }
}

export const runStrictUnsavedCreateNavigationConfirmCopy = async () => {
  let context: BrowserContext | null = null

  try {
    const workspace = await setupQuizWorkspace()
    context = workspace.context

    const unique = Date.now()
    const draftName = `E2E Quiz ${unique} Draft`

    const { page } = workspace
    await openQuizWorkspace(page, workspace.optionsUrl)
    await page.getByRole("tab", { name: /Create/i }).click()

    const createPanel = page
      .getByRole("tabpanel")
      .filter({ has: page.getByRole("button", { name: /Save Quiz/i }) })
      .first()
    await expect(createPanel).toBeVisible({ timeout: 10000 })

    const quizNameInput = createPanel.getByLabel(/Quiz Name/i)
    await quizNameInput.fill(draftName)
    await expect(quizNameInput).toHaveValue(draftName)

    const unsavedDialogHandled = new Promise<void>((resolve, reject) => {
      page.once("dialog", async (dialog) => {
        try {
          expect(dialog.message()).toMatch(UNSAVED_CREATE_PROMPT)
          await dialog.accept()
          resolve()
        } catch (error) {
          reject(error)
        }
      })
    })
    await page.getByRole("tab", { name: /Generate/i }).click()
    await unsavedDialogHandled

    await expect(page.getByText("Select Sources", { exact: true })).toBeVisible({ timeout: 10000 })
  } finally {
    await context?.close()
  }
}

export const runStrictCreateManualQuizFromCreateTab = async () => {
  let context: BrowserContext | null = null
  const quizIds: number[] = []

  try {
    const workspace = await setupQuizWorkspace()
    context = workspace.context

    const unique = Date.now()
    const baseName = `E2E Quiz ${unique}`
    const createdQuizName = `${baseName} Manual`
    const createdQuestionText = `${baseName} Manual Q1: Largest planet?`

    const { page } = workspace
    await openQuizWorkspace(page, workspace.optionsUrl)

    await page.getByRole("tab", { name: /Create/i }).click()
    const createPanel = page
      .getByRole("tabpanel")
      .filter({ has: page.getByRole("button", { name: /Save Quiz/i }) })
      .first()
    await expect(createPanel).toBeVisible({ timeout: 10000 })

    const quizNameInput = createPanel.getByLabel(/Quiz Name/i)
    await quizNameInput.fill(createdQuizName)
    await expect(quizNameInput).toHaveValue(createdQuizName)
    await createPanel.getByLabel(/Description/i).fill("Created via Playwright")
    await createPanel.getByLabel(/Time Limit/i).fill("20")
    await createPanel.getByLabel(/Passing Score/i).fill("75")

    await createPanel.getByRole("button", { name: /Add Your First Question/i }).click()
    const questionCard = createPanel.locator(".ant-card").filter({ hasText: /Question 1/i }).first()
    await expect(questionCard).toBeVisible({ timeout: 10000 })

    await questionCard.getByPlaceholder(/Enter your question/i).fill(createdQuestionText)
    await questionCard.getByPlaceholder(/Option 1/i).fill("Jupiter")
    await questionCard.getByPlaceholder(/Option 2/i).fill("Mars")
    await questionCard.getByPlaceholder(/Option 3/i).fill("Earth")
    await questionCard.getByPlaceholder(/Option 4/i).fill("Venus")
    await questionCard.locator('input[type="radio"]').first().click({ force: true })

    const saveQuizButton = createPanel.getByRole("button", { name: /Save Quiz/i })
    await expect(saveQuizButton).toBeEnabled()
    let createdQuizId: number | null = null
    let createRequestError: RequestErrorEntry | null = null
    for (let attempt = 0; attempt < 3; attempt += 1) {
      await saveQuizButton.click({ force: true })
      createdQuizId = await waitForQuizIdByName(
        workspace.normalizedServerUrl,
        workspace.apiKey,
        createdQuizName
      )
      if (createdQuizId != null) {
        break
      }
      createRequestError = await getLastRequestError(page)
      await waitFor(350)
    }
    const createErrorSummary = createRequestError
      ? ` [lastRequestError method=${createRequestError.method ?? "?"} path=${createRequestError.path ?? "?"} status=${createRequestError.status ?? "?"} error=${createRequestError.error ?? "?"}]`
      : ""
    expect(
      createdQuizId,
      `Created quiz was not observed by API lookup: ${createdQuizName}.${createErrorSummary}`
    ).not.toBeNull()
    expect(createdQuizId).not.toBeNull()
    if (createdQuizId == null) {
      throw new Error(`Created quiz was not observed by API lookup: ${createdQuizName}.${createErrorSummary}`)
    }
    quizIds.push(createdQuizId)

    const persistedQuiz = await apiRequest<QuizApiResponse>(
      workspace.normalizedServerUrl,
      workspace.apiKey,
      `/api/v1/quizzes/${createdQuizId}`
    )
    expect(persistedQuiz.name).toBe(createdQuizName)
    expect(persistedQuiz.description ?? "").toContain("Created via Playwright")
    expect(persistedQuiz.time_limit_seconds).toBe(1200)
    expect(persistedQuiz.passing_score).toBe(75)

    const createdQuestions = await apiRequest<ListResponse<QuestionApiResponse>>(
      workspace.normalizedServerUrl,
      workspace.apiKey,
      `/api/v1/quizzes/${createdQuizId}/questions?include_answers=true&limit=20&offset=0`
    )
    expect(createdQuestions.items.length).toBeGreaterThan(0)
    expect(createdQuestions.items.some((item) => item.question_text === createdQuestionText)).toBeTruthy()

    await page.getByRole("tab", { name: /Manage/i }).click()
    const managePanel = page
      .getByRole("tabpanel")
      .filter({ has: page.getByPlaceholder(/Search quizzes/i) })
    const searchInput = managePanel.getByPlaceholder(/Search quizzes/i)
    await searchInput.fill(createdQuizName)
    await expect(managePanel.getByText(createdQuizName, { exact: true })).toBeVisible({
      timeout: 10000
    })
  } finally {
    if (quizIds.length > 0) {
      const { serverUrl, apiKey } = requireRealServerConfig(test)
      await cleanupQuizzes(normalizeServerUrl(serverUrl), apiKey, quizIds)
    }
    await context?.close()
  }
}

export const runStrictTakeSubmitVerifyResultsFlow = async (testInfo: TestInfo) => {
  let context: BrowserContext | null = null
  const quizIds: number[] = []

  try {
    const workspace = await setupQuizWorkspace()
    context = workspace.context

    const unique = Date.now()
    const baseName = `E2E Quiz ${unique}`
    const fixture = await seedQuizFixture(
      workspace.normalizedServerUrl,
      workspace.apiKey,
      baseName,
      2
    )
    quizIds.push(...fixture.quizIds)

    const { page } = workspace
    await openQuizWorkspace(page, workspace.optionsUrl)

    const globalSearchInput = page.getByPlaceholder(/Search quizzes across tabs/i)
    if ((await globalSearchInput.count()) > 0) {
      await globalSearchInput.fill(fixture.mainQuizName)
      const searchButton = page.getByRole("button", { name: /^Search$/i }).first()
      if ((await searchButton.count()) > 0) {
        await searchButton.click()
      }
    }

    await page.getByRole("tab", { name: /Take Quiz/i }).click()
    await page.getByTestId("take-loading-skeleton").waitFor({ state: "hidden", timeout: 20000 }).catch(() => {})

    const quizCard = await findTakeQuizCard(page, fixture.mainQuizId)
    expect(quizCard).not.toBeNull()
    if (!quizCard) {
      throw new Error(`Could not find take quiz card for quiz ${fixture.mainQuizId}`)
    }

    await expect(quizCard).toBeVisible({ timeout: 15000 })
    const questionItems = page.locator('[data-testid^="quiz-question-"]')
    let questionListVisible = false
    for (let attempt = 0; attempt < 2; attempt += 1) {
      await quizCard
        .getByRole("button", { name: /Start Quiz|Start Practice|Open Review/i })
        .click({ force: true })

      const beginDialog = page.getByRole("dialog").filter({ hasText: /Ready to begin\?/i }).first()
      await expect(beginDialog).toBeVisible({ timeout: 10000 })
      await beginDialog.getByRole("button", { name: /Begin Quiz/i }).click({ force: true })
      await expect(beginDialog).toBeHidden({ timeout: 10000 })

      const startErrorToast = page.getByText(/Failed to start quiz/i).last()
      const hasStartError = await startErrorToast.isVisible({ timeout: 2000 }).catch(() => false)
      if (hasStartError) {
        await waitFor(500)
        continue
      }

      questionListVisible = await questionItems
        .first()
        .isVisible({ timeout: 15000 })
        .catch(() => false)
      if (questionListVisible) {
        break
      }
    }

    if (!questionListVisible) {
      const screenshotPath = testInfo.outputPath("quiz-take-missing-question-list.png")
      await page.screenshot({ path: screenshotPath, fullPage: true })
      throw new Error(
        `Question list did not render after quiz start. Screenshot saved to ${screenshotPath}`
      )
    }

    const questionCount = await questionItems.count()
    expect(questionCount).toBeGreaterThan(0)

    for (let i = 0; i < questionCount; i += 1) {
      const item = questionItems.nth(i)
      const radios = item.locator('input[type="radio"]')
      if ((await radios.count()) > 0) {
        await radios.first().click({ force: true })
        continue
      }

      const textbox = item.getByRole("textbox").first()
      if ((await textbox.count()) > 0) {
        await textbox.fill("E2E answer")
      }
    }

    const submitAttemptResponsePromise = page.waitForResponse((response) => {
      const method = response.request().method().toUpperCase()
      if (method !== "PUT") return false
      try {
        const parsed = new URL(response.url())
        return /^\/api\/v1\/quizzes\/attempts\/\d+$/.test(parsed.pathname)
      } catch {
        return false
      }
    })

    await page.getByRole("button", { name: /Submit/i }).click({ force: true })
    const submitAttemptResponse = await submitAttemptResponsePromise
    expect(submitAttemptResponse.status()).toBe(200)
    const submitAttemptPayload = (await submitAttemptResponse
      .json()
      .catch(() => null)) as { id?: unknown } | null
    const submittedAttemptId =
      submitAttemptPayload && typeof submitAttemptPayload.id === "number"
        ? submitAttemptPayload.id
        : null
    expect(submittedAttemptId, "Submit attempt response did not include numeric id").not.toBeNull()
    if (submittedAttemptId == null) {
      throw new Error("Submit attempt response did not include numeric id")
    }

    await expect(page.getByText(/Score:/i)).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole("button", { name: /Retake Quiz/i })).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/Correct answer/i).first()).toBeVisible({ timeout: 10000 })

    const persistedAttempt = await apiRequest<{
      id: number
      quiz_id: number
      completed_at?: string | null
      score?: number | null
      answers?: Array<unknown>
    }>(
      workspace.normalizedServerUrl,
      workspace.apiKey,
      `/api/v1/quizzes/attempts/${submittedAttemptId}?include_answers=true`
    )
    expect(persistedAttempt.id).toBe(submittedAttemptId)
    expect(persistedAttempt.quiz_id).toBe(fixture.mainQuizId)
    expect(persistedAttempt.completed_at ?? null).not.toBeNull()
    expect(Array.isArray(persistedAttempt.answers)).toBeTruthy()
    expect((persistedAttempt.answers ?? []).length).toBeGreaterThan(0)

    const resultsTab = page.getByRole("tab", { name: /Results/i })
    await resultsTab.click()
    const resultsPanelId = await resultsTab.getAttribute("aria-controls")
    const resultsPanel = resultsPanelId
      ? page.locator(`#${resultsPanelId}`)
      : page.getByRole("tabpanel").filter({ has: resultsTab })

    await expect(resultsPanel).toBeVisible({ timeout: 10000 })
    await resultsPanel.locator(".ant-spin").waitFor({ state: "hidden" })

    const resultsItems = resultsPanel.locator(".ant-list-item")
    const attemptsListPayload = await apiRequest<ListResponse<{ id: number }>>(
      workspace.normalizedServerUrl,
      workspace.apiKey,
      `/api/v1/quizzes/attempts?quiz_id=${fixture.mainQuizId}&limit=5&offset=0`
    )
    expect(attemptsListPayload.items.length).toBeGreaterThan(0)
    expect(attemptsListPayload.items.some((item) => item.id === submittedAttemptId)).toBeTruthy()
    await expect
      .poll(async () => await resultsItems.count(), { timeout: 15000 })
      .toBeGreaterThan(0)
    await expect(resultsItems.first()).toBeVisible({ timeout: 10000 })
    await expect(resultsPanel.getByText(/No quiz attempts yet/i)).toBeHidden()
  } finally {
    if (quizIds.length > 0) {
      const { serverUrl, apiKey } = requireRealServerConfig(test)
      await cleanupQuizzes(normalizeServerUrl(serverUrl), apiKey, quizIds)
    }
    await context?.close()
  }
}
