import React from "react";
import { ChevronDown, ChevronUp, Download, RefreshCcw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  tldwClient,
  type WorldBookProcessDiagnostic,
} from "@/services/tldw/TldwApiClient";
import { downloadBlob } from "@/utils/download-blob";
import {
  DEFAULT_LOREBOOK_TOKEN_BUDGET,
  detectLorebookKeywordConflicts,
  getLorebookBudgetStatus,
} from "@/utils/lorebook-debug";

type Props = {
  serverChatId: string | null;
  settingsFingerprint: string;
};

type LorebookDiagnosticRow = WorldBookProcessDiagnostic & {
  worldBookName: string | null;
};

type LorebookDebugData = {
  entriesMatched: number;
  tokensUsed: number;
  booksUsed: number;
  tokenBudget: number;
  budgetExhausted: boolean;
  skippedEntriesDueToBudget: number;
  diagnostics: LorebookDiagnosticRow[];
};

const normalizeCharacterId = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const toLatestTurnScanText = (
  messages: Array<{ role?: string | null; content?: string | null }>,
): string => {
  const recent = messages
    .filter((msg) => {
      const role = String(msg.role || "").toLowerCase();
      if (role !== "user" && role !== "assistant") return false;
      return String(msg.content || "").trim().length > 0;
    })
    .slice(-8);

  return recent
    .map((msg) => `${String(msg.role || "user")}: ${String(msg.content || "")}`)
    .join("\n")
    .trim();
};

type ChatMessageLite = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
};

const buildTurnScanWindows = (
  messages: ChatMessageLite[],
  maxRecentMessagesPerTurn = 8,
): Array<{
  turnIndex: number;
  assistantMessageId: string;
  assistantCreatedAt: string;
  assistantPreview: string;
  scanText: string;
}> => {
  const relevant = messages.filter((msg) => {
    if (msg.role !== "user" && msg.role !== "assistant") return false;
    return String(msg.content || "").trim().length > 0;
  });

  const windows: Array<{
    turnIndex: number;
    assistantMessageId: string;
    assistantCreatedAt: string;
    assistantPreview: string;
    scanText: string;
  }> = [];

  let turnCounter = 0;
  for (let index = 0; index < relevant.length; index += 1) {
    const message = relevant[index];
    if (message.role !== "assistant") continue;
    turnCounter += 1;
    const start = Math.max(0, index - (maxRecentMessagesPerTurn - 1));
    const windowMessages = relevant.slice(start, index + 1);
    const scanText = toLatestTurnScanText(windowMessages);
    if (!scanText) continue;

    windows.push({
      turnIndex: turnCounter,
      assistantMessageId: message.id,
      assistantCreatedAt: message.created_at,
      assistantPreview: message.content.slice(0, 240),
      scanText,
    });
  }

  return windows;
};

const activationReasonLabel = (
  reason: string,
  fallbackRegexMatch: boolean,
  t: ReturnType<typeof useTranslation>["t"],
): string => {
  if (reason === "depth") {
    return t("playground:composer.lorebookDebug.reasonDepth", {
      defaultValue: "Depth rule",
    });
  }
  if (reason === "regex_match" || fallbackRegexMatch) {
    return t("playground:composer.lorebookDebug.reasonRegex", {
      defaultValue: "Regex match",
    });
  }
  return t("playground:composer.lorebookDebug.reasonKeyword", {
    defaultValue: "Keyword match",
  });
};

export const LorebookDebugPanel: React.FC<Props> = ({
  serverChatId,
  settingsFingerprint,
}) => {
  const { t } = useTranslation(["playground", "common"]);
  const [open, setOpen] = React.useState(false);
  const [isExporting, setIsExporting] = React.useState(false);

  const query = useQuery({
    queryKey: ["lorebookDebugPanel", serverChatId, settingsFingerprint],
    enabled: open && Boolean(serverChatId),
    queryFn: async (): Promise<LorebookDebugData> => {
      if (!serverChatId) {
        return {
          entriesMatched: 0,
          tokensUsed: 0,
          booksUsed: 0,
          tokenBudget: DEFAULT_LOREBOOK_TOKEN_BUDGET,
          budgetExhausted: false,
          skippedEntriesDueToBudget: 0,
          diagnostics: [],
        };
      }

      const chat = await tldwClient.getChat(serverChatId);
      const characterId = normalizeCharacterId(chat?.character_id);
      if (!characterId) {
        return {
          entriesMatched: 0,
          tokensUsed: 0,
          booksUsed: 0,
          tokenBudget: DEFAULT_LOREBOOK_TOKEN_BUDGET,
          budgetExhausted: false,
          skippedEntriesDueToBudget: 0,
          diagnostics: [],
        };
      }

      const messages = await tldwClient.listChatMessages(serverChatId, {
        limit: 80,
        offset: 0,
      });
      const scanText = toLatestTurnScanText(messages);
      if (!scanText) {
        return {
          entriesMatched: 0,
          tokensUsed: 0,
          booksUsed: 0,
          tokenBudget: DEFAULT_LOREBOOK_TOKEN_BUDGET,
          budgetExhausted: false,
          skippedEntriesDueToBudget: 0,
          diagnostics: [],
        };
      }

      const response = await tldwClient.processWorldBookContext({
        text: scanText,
        character_id: characterId,
        scan_depth: 3,
        token_budget: 420,
        recursive_scanning: true,
      });

      let worldBookNameById = new Map<number, string>();
      try {
        const books = await tldwClient.listCharacterWorldBooks(characterId);
        const list = Array.isArray(books) ? books : [];
        worldBookNameById = new Map<number, string>(
          list
            .map((book: any) => {
              const idRaw = book?.world_book_id ?? book?.id;
              const id = Number(idRaw);
              const name = String(book?.name || "").trim();
              if (!Number.isFinite(id) || name.length === 0) return null;
              return [id, name] as const;
            })
            .filter((pair): pair is readonly [number, string] => pair !== null),
        );
      } catch {
        // Best-effort enrichment only.
      }

      const diagnostics: LorebookDiagnosticRow[] = Array.isArray(
        response?.diagnostics,
      )
        ? response.diagnostics.map((entry) => ({
            ...entry,
            worldBookName:
              typeof entry.world_book_id === "number"
                ? worldBookNameById.get(entry.world_book_id) || null
                : null,
          }))
        : [];

      return {
        entriesMatched: Number(
          response?.entries_matched || diagnostics.length || 0,
        ),
        tokensUsed: Number(response?.tokens_used || 0),
        booksUsed: Number(response?.books_used || 0),
        tokenBudget:
          typeof response?.token_budget === "number"
            ? response.token_budget
            : DEFAULT_LOREBOOK_TOKEN_BUDGET,
        budgetExhausted: Boolean(response?.budget_exhausted),
        skippedEntriesDueToBudget: Number(
          response?.skipped_entries_due_to_budget || 0,
        ),
        diagnostics,
      };
    },
    staleTime: 5000,
  });

  const payload = query.data;
  const budgetStatus = React.useMemo(
    () =>
      payload
        ? getLorebookBudgetStatus({
            tokensUsed: payload.tokensUsed,
            tokenBudget: payload.tokenBudget,
            budgetExhausted: payload.budgetExhausted,
            skippedEntriesDueToBudget: payload.skippedEntriesDueToBudget,
          })
        : null,
    [payload],
  );
  const keywordConflicts = React.useMemo(
    () => detectLorebookKeywordConflicts(payload?.diagnostics),
    [payload?.diagnostics],
  );

  const handleExportDiagnostics = React.useCallback(async () => {
    if (!serverChatId || isExporting) return;

    setIsExporting(true);
    try {
      const chat = await tldwClient.getChat(serverChatId);
      const characterId = normalizeCharacterId(chat?.character_id);
      if (!characterId) {
        return;
      }

      const rawMessages = await tldwClient.listChatMessages(serverChatId, {
        limit: 2000,
        offset: 0,
      });
      const messages = Array.isArray(rawMessages)
        ? (rawMessages as ChatMessageLite[])
        : [];
      const windows = buildTurnScanWindows(messages);
      const maxTurnsForExport = 120;
      const truncated = windows.length > maxTurnsForExport;
      const selectedWindows = truncated
        ? windows.slice(-maxTurnsForExport)
        : windows;

      const books = await tldwClient
        .listCharacterWorldBooks(characterId)
        .catch(() => []);
      const list = Array.isArray(books) ? books : [];
      const worldBookNameById = new Map<number, string>(
        list
          .map((book: any) => {
            const idRaw = book?.world_book_id ?? book?.id;
            const id = Number(idRaw);
            const name = String(book?.name || "").trim();
            if (!Number.isFinite(id) || name.length === 0) return null;
            return [id, name] as const;
          })
          .filter((pair): pair is readonly [number, string] => pair !== null),
      );

      const turns: Array<Record<string, unknown>> = [];
      for (const window of selectedWindows) {
        const response = await tldwClient.processWorldBookContext({
          text: window.scanText,
          character_id: characterId,
          scan_depth: 3,
          token_budget: DEFAULT_LOREBOOK_TOKEN_BUDGET,
          recursive_scanning: true,
        });

        const diagnostics = Array.isArray(response?.diagnostics)
          ? response.diagnostics.map((entry) => ({
              ...entry,
              world_book_name:
                typeof entry.world_book_id === "number"
                  ? worldBookNameById.get(entry.world_book_id) || null
                  : null,
            }))
          : [];
        const status = getLorebookBudgetStatus({
          tokensUsed: Number(response?.tokens_used || 0),
          tokenBudget:
            typeof response?.token_budget === "number"
              ? response.token_budget
              : DEFAULT_LOREBOOK_TOKEN_BUDGET,
          budgetExhausted: Boolean(response?.budget_exhausted),
          skippedEntriesDueToBudget: Number(
            response?.skipped_entries_due_to_budget || 0,
          ),
        });
        const conflicts = detectLorebookKeywordConflicts(diagnostics);

        turns.push({
          turn_index: window.turnIndex,
          assistant_message_id: window.assistantMessageId,
          assistant_created_at: window.assistantCreatedAt,
          assistant_preview: window.assistantPreview,
          entries_matched: Number(response?.entries_matched || 0),
          tokens_used: status.tokensUsed,
          token_budget: status.tokenBudget,
          budget_exhausted: status.budgetExhausted,
          skipped_entries_due_to_budget: status.skippedEntriesDueToBudget,
          conflicts,
          diagnostics,
        });
      }

      const exportPayload = {
        exported_at: new Date().toISOString(),
        chat_id: serverChatId,
        character_id: characterId,
        turns_total: windows.length,
        turns_exported: selectedWindows.length,
        turns_truncated: truncated,
        turns,
      };

      const blob = new Blob([JSON.stringify(exportPayload, null, 2)], {
        type: "application/json;charset=utf-8",
      });
      downloadBlob(blob, `lorebook-diagnostics-${serverChatId}.json`);
    } finally {
      setIsExporting(false);
    }
  }, [isExporting, serverChatId]);

  return (
    <div className="rounded-lg border border-border/60 bg-surface2/40">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-left"
        onClick={() => setOpen((value) => !value)}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text">
            {t("playground:composer.lorebookDebug.title", {
              defaultValue: "Lorebook Debug",
            })}
          </span>
          {payload && (
            <span className="rounded-full border border-border/60 bg-surface2 px-2 py-0.5 text-[11px] text-text-muted">
              {payload.tokensUsed}{" "}
              {t("playground:composer.lorebookDebug.tokensUsed", {
                defaultValue: "tokens",
              })}
            </span>
          )}
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-text-muted" />
        ) : (
          <ChevronDown className="h-4 w-4 text-text-muted" />
        )}
      </button>

      {open && (
        <div className="border-t border-border/60 px-3 py-3 text-xs">
          {!serverChatId && (
            <p className="text-text-muted">
              {t("playground:composer.lorebookDebug.serverBackedOnly", {
                defaultValue:
                  "Lorebook debug is available after this chat is saved to server.",
              })}
            </p>
          )}

          {serverChatId && (
            <>
              <div className="mb-2 flex items-center justify-end">
                <div className="inline-flex items-center gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded border border-border/60 px-2 py-1 text-[11px] text-text-muted hover:border-primary/50 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => void query.refetch()}
                    disabled={query.isFetching || isExporting}
                  >
                    <RefreshCcw className="h-3 w-3" />
                    {t("common:refresh", { defaultValue: "Refresh" })}
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded border border-border/60 px-2 py-1 text-[11px] text-text-muted hover:border-primary/50 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => void handleExportDiagnostics()}
                    disabled={query.isFetching || isExporting}
                  >
                    <Download className="h-3 w-3" />
                    {t("playground:composer.lorebookDebug.export", {
                      defaultValue: "Export log",
                    })}
                  </button>
                </div>
              </div>

              {query.isLoading && (
                <p className="text-text-muted">
                  {t("playground:composer.lorebookDebug.loading", {
                    defaultValue: "Loading lorebook diagnostics...",
                  })}
                </p>
              )}

              {query.isError && (
                <p className="text-danger">
                  {t("playground:composer.lorebookDebug.error", {
                    defaultValue: "Failed to load lorebook diagnostics.",
                  })}
                </p>
              )}

              {!query.isLoading && !query.isError && payload && (
                <div className="space-y-3">
                  <div className="rounded-md border border-border/60 bg-surface2/70 px-2 py-1 text-text-muted">
                    {t("playground:composer.lorebookDebug.summary", {
                      defaultValue:
                        "{{entries}} entries · {{books}} books · {{tokens}} tokens",
                      entries: payload.entriesMatched,
                      books: payload.booksUsed,
                      tokens: payload.tokensUsed,
                    })}
                  </div>

                  {budgetStatus &&
                    (budgetStatus.budgetExhausted ||
                      budgetStatus.skippedEntriesDueToBudget > 0 ||
                      budgetStatus.isCaution) && (
                      <div className="rounded-md border border-warn/40 bg-warn/10 p-2 text-text">
                        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-warn">
                          {t(
                            "playground:composer.lorebookDebug.budgetWarningTitle",
                            {
                              defaultValue: "Budget warning",
                            },
                          )}
                        </div>
                        <p>
                          {budgetStatus.budgetExhausted ||
                          budgetStatus.skippedEntriesDueToBudget > 0
                            ? t(
                                "playground:composer.lorebookDebug.budgetWarningExhausted",
                                {
                                  defaultValue:
                                    "Lorebook token budget is exhausted. {{skipped}} entries were skipped.",
                                  skipped:
                                    budgetStatus.skippedEntriesDueToBudget,
                                },
                              )
                            : t(
                                "playground:composer.lorebookDebug.budgetWarningCaution",
                                {
                                  defaultValue:
                                    "Lorebook token usage is near budget ({{used}}/{{budget}}).",
                                  used: budgetStatus.tokensUsed,
                                  budget: budgetStatus.tokenBudget,
                                },
                              )}
                        </p>
                      </div>
                    )}

                  {keywordConflicts.length > 0 && (
                    <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-text">
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-danger">
                        {t("playground:composer.lorebookDebug.conflictsTitle", {
                          defaultValue: "Potential conflicts",
                        })}
                      </div>
                      <ul className="list-disc space-y-1 pl-4">
                        {keywordConflicts.map((conflict) => (
                          <li key={conflict.keyword}>
                            {t(
                              "playground:composer.lorebookDebug.conflictKeyword",
                              {
                                defaultValue:
                                  "Keyword '{{keyword}}' triggered {{count}} entries.",
                                keyword: conflict.keyword,
                                count: conflict.count,
                              },
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {payload.diagnostics.length === 0 ? (
                    <p className="text-text-muted">
                      {t("playground:composer.lorebookDebug.empty", {
                        defaultValue:
                          "No lorebook entries triggered for the latest turn.",
                      })}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {payload.diagnostics.map((entry, index) => (
                        <div
                          key={`${entry.entry_id ?? "entry"}-${index}`}
                          className="rounded-md border border-border/60 bg-surface2/70 p-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-text-muted">
                            <span>
                              {entry.worldBookName ||
                                t(
                                  "playground:composer.lorebookDebug.unknownBook",
                                  {
                                    defaultValue: "World book",
                                  },
                                )}{" "}
                              · #{entry.entry_id ?? "?"}
                            </span>
                            <span>{entry.token_cost} tokens</span>
                          </div>
                          <div className="mt-1 text-text">
                            {activationReasonLabel(
                              entry.activation_reason,
                              entry.regex_match,
                              t,
                            )}
                            {entry.keyword ? ` · ${entry.keyword}` : ""}
                            {typeof entry.depth_level === "number"
                              ? ` · depth ${entry.depth_level}`
                              : ""}
                          </div>
                          {entry.content_preview?.trim().length > 0 && (
                            <p className="mt-1 whitespace-pre-wrap text-text-subtle">
                              {entry.content_preview}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
