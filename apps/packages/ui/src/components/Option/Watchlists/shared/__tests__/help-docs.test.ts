import { describe, expect, it } from "vitest"
import {
  WATCHLISTS_HELP_DOCS,
  WATCHLISTS_ISSUE_REPORT_URL,
  WATCHLISTS_MAIN_DOCS_URL,
  WATCHLISTS_TAB_HELP_DOCS,
  isValidWatchlistsHelpDocUrl
} from "../help-docs"

describe("watchlists help docs registry", () => {
  it("contains only valid https documentation links", () => {
    for (const [topic, url] of Object.entries(WATCHLISTS_HELP_DOCS)) {
      expect(isValidWatchlistsHelpDocUrl(url), `invalid docs url for ${topic}`).toBe(true)
    }
  })

  it("includes valid route-level docs and issue-report links", () => {
    expect(isValidWatchlistsHelpDocUrl(WATCHLISTS_MAIN_DOCS_URL)).toBe(true)
    expect(isValidWatchlistsHelpDocUrl(WATCHLISTS_ISSUE_REPORT_URL)).toBe(true)
  })

  it("maps each major tab to a valid help destination", () => {
    for (const [tab, url] of Object.entries(WATCHLISTS_TAB_HELP_DOCS)) {
      expect(isValidWatchlistsHelpDocUrl(url), `invalid docs url for ${tab}`).toBe(true)
    }
  })
})
