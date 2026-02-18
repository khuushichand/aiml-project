import { describe, expect, it } from "vitest"

import {
  TRASH_AUTO_PURGE_DAYS,
  filterTrashPromptsByName,
  getTrashDaysRemaining,
  getTrashRemainingSeverity
} from "../trash-prompts-utils"

describe("trash prompt utils", () => {
  it("filters trash prompts by name/title case-insensitively", () => {
    const prompts = [
      { id: "1", name: "Writeup Draft" },
      { id: "2", title: "Bug triage notes" },
      { id: "3", name: "Random" }
    ]

    expect(filterTrashPromptsByName(prompts, "draft")).toEqual([prompts[0]])
    expect(filterTrashPromptsByName(prompts, "TRIAGE")).toEqual([prompts[1]])
    expect(filterTrashPromptsByName(prompts, "")).toEqual(prompts)
  })

  it("calculates days remaining until auto-purge with lower bound at zero", () => {
    const now = Date.UTC(2026, 1, 18, 12, 0, 0)
    const dayMs = 24 * 60 * 60 * 1000

    expect(getTrashDaysRemaining(now, now)).toBe(TRASH_AUTO_PURGE_DAYS)
    expect(getTrashDaysRemaining(now - 29 * dayMs, now)).toBe(1)
    expect(getTrashDaysRemaining(now - 30 * dayMs, now)).toBe(0)
    expect(getTrashDaysRemaining(now - 45 * dayMs, now)).toBe(0)
  })

  it("maps remaining-day thresholds to severity states", () => {
    expect(getTrashRemainingSeverity(20)).toBe("normal")
    expect(getTrashRemainingSeverity(14)).toBe("warning")
    expect(getTrashRemainingSeverity(8)).toBe("warning")
    expect(getTrashRemainingSeverity(7)).toBe("danger")
    expect(getTrashRemainingSeverity(0)).toBe("danger")
  })
})
