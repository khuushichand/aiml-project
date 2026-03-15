import { test, type TestInfo } from "@playwright/test"
import { runStrictTakeSubmitVerifyResultsFlow } from "./utils/quiz-critical-helpers"

test("strictly starts, submits, and verifies take/results flow", async ({}, testInfo: TestInfo) => {
  test.setTimeout(120000)
  await runStrictTakeSubmitVerifyResultsFlow(testInfo)
})
