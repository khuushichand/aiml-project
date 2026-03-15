import { test } from "@playwright/test"
import { runStrictEditQuizMetadataAndQuestionSet } from "./utils/quiz-critical-helpers"

test("strictly edits quiz metadata and question set", async () => {
  test.setTimeout(120000)
  await runStrictEditQuizMetadataAndQuestionSet()
})
