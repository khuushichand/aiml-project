import type { WorldBookProcessDiagnostic } from "@/services/tldw/TldwApiClient";

export const DEFAULT_LOREBOOK_TOKEN_BUDGET = 420;
export const LOREBOOK_BUDGET_CAUTION_RATIO = 0.9;

export type LorebookKeywordConflict = {
  keyword: string;
  count: number;
  entryIds: number[];
};

export type LorebookBudgetStatus = {
  tokenBudget: number;
  tokensUsed: number;
  budgetExhausted: boolean;
  skippedEntriesDueToBudget: number;
  isCaution: boolean;
};

export const getLorebookBudgetStatus = (params: {
  tokensUsed: number;
  tokenBudget?: number | null;
  budgetExhausted?: boolean | null;
  skippedEntriesDueToBudget?: number | null;
}): LorebookBudgetStatus => {
  const tokenBudget =
    typeof params.tokenBudget === "number" && params.tokenBudget > 0
      ? params.tokenBudget
      : DEFAULT_LOREBOOK_TOKEN_BUDGET;
  const tokensUsed =
    typeof params.tokensUsed === "number" && Number.isFinite(params.tokensUsed)
      ? Math.max(0, Math.floor(params.tokensUsed))
      : 0;
  const skippedEntriesDueToBudget =
    typeof params.skippedEntriesDueToBudget === "number" &&
    Number.isFinite(params.skippedEntriesDueToBudget)
      ? Math.max(0, Math.floor(params.skippedEntriesDueToBudget))
      : 0;
  const budgetExhausted =
    Boolean(params.budgetExhausted) || tokensUsed >= tokenBudget;
  const cautionThreshold = Math.floor(
    tokenBudget * LOREBOOK_BUDGET_CAUTION_RATIO,
  );
  const isCaution = !budgetExhausted && tokensUsed >= cautionThreshold;

  return {
    tokenBudget,
    tokensUsed,
    budgetExhausted,
    skippedEntriesDueToBudget,
    isCaution,
  };
};

const normalizeKeyword = (value: unknown): string => {
  if (typeof value !== "string") return "";
  return value.trim().toLowerCase();
};

export const detectLorebookKeywordConflicts = (
  diagnostics: WorldBookProcessDiagnostic[] | null | undefined,
): LorebookKeywordConflict[] => {
  if (!Array.isArray(diagnostics) || diagnostics.length === 0) {
    return [];
  }

  const byKeyword = new Map<string, { count: number; entryIds: number[] }>();
  for (const item of diagnostics) {
    const keyword = normalizeKeyword(item.keyword);
    if (!keyword) continue;

    const existing = byKeyword.get(keyword) || { count: 0, entryIds: [] };
    existing.count += 1;
    if (typeof item.entry_id === "number") {
      existing.entryIds.push(item.entry_id);
    }
    byKeyword.set(keyword, existing);
  }

  return Array.from(byKeyword.entries())
    .filter(([, value]) => value.count > 1)
    .map(([keyword, value]) => ({
      keyword,
      count: value.count,
      entryIds: Array.from(new Set(value.entryIds)),
    }))
    .sort((a, b) => b.count - a.count || a.keyword.localeCompare(b.keyword));
};
