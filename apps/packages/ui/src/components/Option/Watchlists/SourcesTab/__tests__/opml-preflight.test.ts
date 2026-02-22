import { describe, expect, it } from "vitest"
import { buildOpmlPreflightSummary } from "../opml-preflight"

describe("opml preflight", () => {
  it("classifies ready, duplicate and invalid entries", () => {
    const opml = `
      <opml version="1.0">
        <body>
          <outline text="Tech" xmlUrl="https://example.com/tech.xml" />
          <outline text="Tech Duplicate" xmlUrl="https://example.com/tech.xml" />
          <outline text="Broken" xmlUrl="not-a-url" />
          <outline text="Missing URL" />
        </body>
      </opml>
    `

    const summary = buildOpmlPreflightSummary(opml, {
      existingUrls: ["https://existing.com/feed.xml"]
    })

    expect(summary.total).toBe(4)
    expect(summary.ready).toBe(1)
    expect(summary.duplicateFile).toBe(1)
    expect(summary.invalidUrl).toBe(1)
    expect(summary.missingUrl).toBe(1)
    expect(summary.duplicateExisting).toBe(0)
    expect(summary.parseError).toBe(false)
  })

  it("flags duplicates against existing feeds", () => {
    const opml = `
      <opml version="1.0">
        <body>
          <outline text="Existing" xmlUrl="https://existing.com/feed.xml" />
          <outline text="Fresh" xmlUrl="https://new.com/feed.xml" />
        </body>
      </opml>
    `

    const summary = buildOpmlPreflightSummary(opml, {
      existingUrls: ["https://existing.com/feed.xml"]
    })

    expect(summary.ready).toBe(1)
    expect(summary.duplicateExisting).toBe(1)
  })

  it("reports parse error when no OPML outlines are present", () => {
    const summary = buildOpmlPreflightSummary("<not-opml />")
    expect(summary.total).toBe(0)
    expect(summary.parseError).toBe(true)
  })
})
