import { describe, expect, it } from "vitest"
import type { WritingLogprobEntry } from "../writing-logprob-utils"
import {
  buildResponseInspectorCsv,
  selectResponseInspectorRows
} from "../writing-response-inspector-utils"

const SAMPLE_ROWS: WritingLogprobEntry[] = [
  {
    token: " hello",
    logprob: -0.2,
    topLogprobs: [
      { token: " hello", logprob: -0.2 },
      { token: " hi", logprob: -0.8 }
    ]
  },
  {
    token: "\n",
    logprob: -0.1,
    topLogprobs: [{ token: "\n", logprob: -0.1 }]
  },
  {
    token: "world",
    logprob: -1.1,
    topLogprobs: [{ token: "word", logprob: -1.0 }]
  }
]

describe("writing response inspector utils", () => {
  it("filters rows by query and excludes whitespace-only tokens when requested", () => {
    const rows = selectResponseInspectorRows(SAMPLE_ROWS, {
      query: "wo",
      hideWhitespaceOnly: true,
      sort: "sequence",
      maxRows: 50
    })
    expect(rows).toEqual([
      expect.objectContaining({
        token: "world",
        sequence: 2
      })
    ])
  })

  it("sorts rows by descending logprob", () => {
    const rows = selectResponseInspectorRows(SAMPLE_ROWS, {
      query: "",
      hideWhitespaceOnly: false,
      sort: "logprob_desc",
      maxRows: 50
    })
    expect(rows.map((row) => row.token)).toEqual(["\\n", " hello", "world"])
  })

  it("hides whitespace-only tokens when enabled", () => {
    const rows = selectResponseInspectorRows(SAMPLE_ROWS, {
      query: "",
      hideWhitespaceOnly: true,
      sort: "sequence",
      maxRows: 50
    })
    expect(rows.map((row) => row.token)).toEqual([" hello", "world"])
  })

  it("builds csv output with escaped token and alternatives", () => {
    const csv = buildResponseInspectorCsv(
      selectResponseInspectorRows(SAMPLE_ROWS, {
        query: "",
        hideWhitespaceOnly: false,
        sort: "sequence",
        maxRows: 50
      })
    )
    expect(csv).toContain("index,token,logprob,probability,top_alternatives")
    expect(csv).toContain("\"\\n\"")
    expect(csv).toContain("\" hello (-0.200) |  hi (-0.800)\"")
  })
})
