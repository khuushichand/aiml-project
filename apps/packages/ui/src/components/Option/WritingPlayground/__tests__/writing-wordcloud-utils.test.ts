import { describe, expect, it } from "vitest"
import {
  normalizeWordcloudWords,
  parseWordcloudStopwordsInput
} from "../writing-wordcloud-utils"

describe("writing wordcloud utils", () => {
  it("parses stopwords from comma/newline input", () => {
    expect(parseWordcloudStopwordsInput("the, and\nof\n\nfoo")).toEqual([
      "the",
      "and",
      "of",
      "foo"
    ])
  })

  it("normalizes and truncates wordcloud words", () => {
    const words = normalizeWordcloudWords(
      [
        { text: "beta", weight: 2 },
        { text: "alpha", weight: 5 },
        { text: "", weight: 3 },
        { text: "gamma", weight: 0 }
      ],
      2
    )
    expect(words).toEqual([
      { text: "alpha", weight: 5 },
      { text: "beta", weight: 2 }
    ])
  })
})
