import { test } from "@playwright/test"
import {
  runStrictCreateManualQuizFromCreateTab,
  runStrictUnsavedCreateNavigationConfirmCopy
} from "./utils/quiz-critical-helpers"

test("strictly enforces unsaved-create navigation confirm copy", async () => {
  test.setTimeout(90000)
  await runStrictUnsavedCreateNavigationConfirmCopy()
})

test("strictly creates a manual quiz from create tab", async () => {
  test.setTimeout(120000)
  await runStrictCreateManualQuizFromCreateTab()
})
