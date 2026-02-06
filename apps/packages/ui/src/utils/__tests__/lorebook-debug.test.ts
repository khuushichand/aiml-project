import { describe, expect, it } from "vitest";
import {
  DEFAULT_LOREBOOK_TOKEN_BUDGET,
  detectLorebookKeywordConflicts,
  getLorebookBudgetStatus,
} from "../lorebook-debug";

describe("lorebook debug utility", () => {
  it("marks caution near budget threshold", () => {
    const status = getLorebookBudgetStatus({
      tokensUsed: Math.floor(DEFAULT_LOREBOOK_TOKEN_BUDGET * 0.9),
      tokenBudget: DEFAULT_LOREBOOK_TOKEN_BUDGET,
    });
    expect(status.isCaution).toBe(true);
    expect(status.budgetExhausted).toBe(false);
  });

  it("marks exhausted when tokens reach budget", () => {
    const status = getLorebookBudgetStatus({
      tokensUsed: DEFAULT_LOREBOOK_TOKEN_BUDGET,
      tokenBudget: DEFAULT_LOREBOOK_TOKEN_BUDGET,
    });
    expect(status.budgetExhausted).toBe(true);
    expect(status.isCaution).toBe(false);
  });

  it("detects repeated keyword conflicts across diagnostics", () => {
    const conflicts = detectLorebookKeywordConflicts([
      {
        entry_id: 1,
        world_book_id: 10,
        activation_reason: "keyword_match",
        keyword: "dragon",
        token_cost: 12,
        priority: 1,
        regex_match: false,
        content_preview: "one",
      },
      {
        entry_id: 2,
        world_book_id: 10,
        activation_reason: "keyword_match",
        keyword: "DRAGON",
        token_cost: 10,
        priority: 1,
        regex_match: false,
        content_preview: "two",
      },
      {
        entry_id: 3,
        world_book_id: 11,
        activation_reason: "keyword_match",
        keyword: "mage",
        token_cost: 8,
        priority: 1,
        regex_match: false,
        content_preview: "three",
      },
    ]);

    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].keyword).toBe("dragon");
    expect(conflicts[0].count).toBe(2);
    expect(conflicts[0].entryIds).toEqual([1, 2]);
  });
});
