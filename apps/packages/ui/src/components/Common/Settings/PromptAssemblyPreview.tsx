import React from "react"
import { ChevronDown, ChevronUp, RefreshCcw } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useStoreMessageOption } from "@/store/option"
import { resolveMessageSteering } from "@/utils/message-steering"

export type PromptPreviewConflict = {
  type: string
  message: string
}

export type PromptPreviewSection = {
  key: string
  label: string
  active: boolean
  tokens: number
  preview: string
}

export type PromptPreviewSummary = {
  sections: PromptPreviewSection[]
  supplementalTokens: number
  supplementalBudget: number
  budgetStatus: "ok" | "caution" | "error"
  warnings: string[]
  conflicts: PromptPreviewConflict[]
  examples: string[]
}

type Props = {
  serverChatId: string | null
  settingsFingerprint: string
}

interface PromptPreviewSectionPayload {
  name?: unknown
  content?: unknown
  tokens_effective?: unknown
  tokens_estimated?: unknown
}

interface PromptPreviewConflictPayload {
  type?: unknown
  message?: unknown
}

interface PromptPreviewPayload {
  sections?: unknown
  supplemental_budget?: unknown
  total_supplemental_effective_tokens?: unknown
  total_supplemental_tokens?: unknown
  budget_status?: unknown
  warnings?: unknown
  conflicts?: unknown
  examples?: unknown
}

const toObject = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null

const toSectionPayload = (value: unknown): PromptPreviewSectionPayload =>
  (toObject(value) as PromptPreviewSectionPayload | null) ?? {}

const toConflictPayload = (value: unknown): PromptPreviewConflictPayload =>
  (toObject(value) as PromptPreviewConflictPayload | null) ?? {}

const getBudgetToneClass = (status: PromptPreviewSummary["budgetStatus"]) => {
  if (status === "error") return "text-danger border-danger/40 bg-danger/10"
  if (status === "caution") return "text-warn border-warn/40 bg-warn/10"
  return "text-text-muted border-border/60 bg-surface2"
}

const SECTION_I18N_KEYS: Record<string, string> = {
  preset: "playground:section.preset",
  author_note: "playground:section.author_note",
  message_steering: "playground:section.message_steering",
  greeting: "playground:section.greeting",
  lorebook: "playground:section.lorebook",
  world_book: "playground:section.world_book"
}

const toBudgetStatus = (
  value: PromptPreviewPayload["budget_status"],
  supplementalTokens: number,
  supplementalBudget: number
): PromptPreviewSummary["budgetStatus"] => {
  if (value === "error" || value === "caution" || value === "ok") return value
  if (supplementalTokens >= supplementalBudget) return "error"
  if (supplementalTokens >= Math.floor(supplementalBudget * 0.9)) return "caution"
  return "ok"
}

export const normalizePreviewPayload = (payload: unknown): PromptPreviewSummary => {
  const parsedPayload = (toObject(payload) as PromptPreviewPayload | null) ?? {}
  const sectionList = Array.isArray(parsedPayload.sections)
    ? parsedPayload.sections
    : []
  const sections = sectionList.map((rawSection) => {
    const section = toSectionPayload(rawSection)
    const key = String(section.name || "unknown")
    const content = typeof section.content === "string" ? section.content : ""
    const label = key.replace(/_/g, " ")
    const tokens =
      typeof section.tokens_effective === "number"
        ? section.tokens_effective
        : typeof section.tokens_estimated === "number"
          ? section.tokens_estimated
          : 0
    return {
      key,
      label,
      active: content.trim().length > 0 || tokens > 0,
      tokens,
      preview: content
    } as PromptPreviewSection
  })

  const supplementalBudget =
    typeof parsedPayload.supplemental_budget === "number"
      ? parsedPayload.supplemental_budget
      : 1200
  const supplementalTokens =
    typeof parsedPayload.total_supplemental_effective_tokens === "number"
      ? parsedPayload.total_supplemental_effective_tokens
      : typeof parsedPayload.total_supplemental_tokens === "number"
        ? parsedPayload.total_supplemental_tokens
        : sections.reduce((total, section) => total + section.tokens, 0)
  const budgetStatus = toBudgetStatus(
    parsedPayload.budget_status,
    supplementalTokens,
    supplementalBudget
  )
  const warnings = Array.isArray(parsedPayload.warnings)
    ? parsedPayload.warnings.filter((value: unknown) => typeof value === "string")
    : []
  const conflicts = Array.isArray(parsedPayload.conflicts)
    ? parsedPayload.conflicts
        .map((rawConflict) => {
          const conflict = toConflictPayload(rawConflict)
          return {
            type: String(conflict.type || "directive_conflict"),
            message: String(conflict.message || "")
          }
        })
        .filter((item: PromptPreviewConflict) => item.message.length > 0)
    : []
  const examples = Array.isArray(parsedPayload.examples)
    ? parsedPayload.examples.filter((value: unknown) => typeof value === "string")
    : []

  return {
    sections,
    supplementalTokens,
    supplementalBudget,
    budgetStatus,
    warnings,
    conflicts,
    examples
  }
}

export const PromptAssemblyPreview: React.FC<Props> = ({
  serverChatId,
  settingsFingerprint
}) => {
  const { t } = useTranslation(["playground", "common"])
  const [open, setOpen] = React.useState(false)
  const { messageSteeringMode, messageSteeringForceNarrate } =
    useStoreMessageOption()
  const resolvedSteering = React.useMemo(
    () =>
      resolveMessageSteering({
        mode: messageSteeringMode,
        forceNarrate: messageSteeringForceNarrate
      }),
    [messageSteeringForceNarrate, messageSteeringMode]
  )

  const query = useQuery({
    queryKey: [
      "promptAssemblyPreview",
      serverChatId,
      settingsFingerprint,
      resolvedSteering.mode,
      resolvedSteering.forceNarrate
    ],
    enabled: open && Boolean(serverChatId),
    queryFn: async () => {
      if (!serverChatId) {
        return null
      }
      const payload = await tldwClient.getCharacterPromptPreview(serverChatId, {
        include_character_context: true,
        limit: 250,
        offset: 0,
        continue_as_user: resolvedSteering.continueAsUser,
        impersonate_user: resolvedSteering.impersonateUser,
        force_narrate: resolvedSteering.forceNarrate
      })
      return normalizePreviewPayload(payload)
    },
    staleTime: 5000
  })

  const preview = query.data

  return (
    <div className="rounded-lg border border-border/60 bg-surface2/40">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-left"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="prompt-assembly-preview-panel"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text">
            {t("playground:composer.promptPreview.title", {
              defaultValue: "Prompt preview"
            })}
          </span>
          {preview && (
            <span
              className={`rounded-full border px-2 py-0.5 text-[11px] ${getBudgetToneClass(
                preview.budgetStatus
              )}`}
            >
              {preview.supplementalTokens}/{preview.supplementalBudget}{" "}
              {t("playground:composer.promptPreview.tokens", {
                defaultValue: "tokens"
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
        <div
          id="prompt-assembly-preview-panel"
          className="border-t border-border/60 px-3 py-3 text-xs"
        >
          {!serverChatId && (
            <p className="text-text-muted">
              {t("playground:composer.promptPreview.serverBackedOnly", {
                defaultValue:
                  "Prompt preview is available after this chat is saved to server."
              })}
            </p>
          )}

          {serverChatId && (
            <>
              <div className="mb-2 flex items-center justify-end">
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded border border-border/60 px-2 py-1 text-[11px] text-text-muted hover:border-primary/50 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => void query.refetch()}
                  disabled={query.isFetching}
                >
                  <RefreshCcw className="h-3 w-3" />
                  {t("common:refresh", { defaultValue: "Refresh" })}
                </button>
              </div>

              {query.isLoading && (
                <p className="text-text-muted">
                  {t("playground:composer.promptPreview.loading", {
                    defaultValue: "Loading preview..."
                  })}
                </p>
              )}

              {query.isError && (
                <p className="text-danger">
                  {t("playground:composer.promptPreview.error", {
                    defaultValue: "Failed to load prompt preview."
                  })}
                </p>
              )}

              {!query.isLoading && !query.isError && preview && (
                <div className="space-y-3">
                  <div className="overflow-hidden rounded-md border border-border/60">
                    <table className="w-full border-collapse text-xs">
                      <thead>
                        <tr className="bg-surface2 text-left text-text-muted">
                          <th className="px-2 py-1 font-medium">
                            {t("playground:composer.promptPreview.section", {
                              defaultValue: "Section"
                            })}
                          </th>
                          <th className="px-2 py-1 font-medium">
                            {t("playground:composer.promptPreview.active", {
                              defaultValue: "Active"
                            })}
                          </th>
                          <th className="px-2 py-1 text-right font-medium">
                            {t("playground:composer.promptPreview.tokenCount", {
                              defaultValue: "Tokens"
                            })}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.sections.map((section) => (
                          <tr
                            key={section.key}
                            className="border-t border-border/60 text-text"
                          >
                            <td className="px-2 py-1">
                              {SECTION_I18N_KEYS[section.key]
                                ? t(SECTION_I18N_KEYS[section.key], { defaultValue: section.label })
                                : section.label}
                            </td>
                            <td className="px-2 py-1">
                              <span
                                className={
                                  section.active
                                    ? "text-success"
                                    : "text-text-subtle"
                                }
                              >
                                {section.active
                                  ? t("common:yes", { defaultValue: "Yes" })
                                  : t("common:no", { defaultValue: "No" })}
                              </span>
                            </td>
                            <td className="px-2 py-1 text-right tabular-nums">
                              {section.tokens}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {preview.warnings.length > 0 && (
                    <div className="rounded-md border border-warn/40 bg-warn/10 p-2 text-text">
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-warn">
                        {t("playground:composer.promptPreview.warnings", {
                          defaultValue: "Warnings"
                        })}
                      </div>
                      <ul className="list-disc space-y-1 pl-4">
                        {preview.warnings.map((warning, index) => (
                          <li key={`${warning}-${index}`}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {preview.conflicts.length > 0 && (
                    <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-text">
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-danger">
                        {t("playground:composer.promptPreview.conflicts", {
                          defaultValue: "Potential conflicts"
                        })}
                      </div>
                      <ul className="list-disc space-y-1 pl-4">
                        {preview.conflicts.map((conflict, index) => (
                          <li key={`${conflict.type}-${index}`}>{conflict.message}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {preview.sections
                    .filter((section) => section.active && section.preview.length > 0)
                    .map((section) => (
                      <div
                        key={`${section.key}-preview`}
                        className="rounded-md border border-border/60 bg-surface2/70 p-2"
                      >
                        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                          {SECTION_I18N_KEYS[section.key]
                            ? t(SECTION_I18N_KEYS[section.key], { defaultValue: section.label })
                            : section.label}
                        </div>
                        <p className="whitespace-pre-wrap text-text">
                          {section.preview}
                        </p>
                      </div>
                    ))}

                  {preview.examples.length > 0 && (
                    <div className="rounded-md border border-border/60 bg-surface2/70 p-2 text-text">
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                        {t("playground:composer.promptPreview.examples", {
                          defaultValue: "Conflict resolution examples"
                        })}
                      </div>
                      <ul className="list-disc space-y-1 pl-4">
                        {preview.examples.map((example, index) => (
                          <li key={`${example}-${index}`}>{example}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
