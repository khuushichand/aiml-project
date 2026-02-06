import React from "react"
import { ChevronDown, ChevronUp, RefreshCcw } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useStoreMessageOption } from "@/store/option"
import { resolveMessageSteering } from "@/utils/message-steering"
import {
  buildPromptPreviewSummary,
  type PromptPreviewSummary
} from "@/utils/prompt-preview"

type Props = {
  serverChatId: string | null
  settingsFingerprint: string
}

const getBudgetToneClass = (status: PromptPreviewSummary["budgetStatus"]) => {
  if (status === "error") return "text-danger border-danger/40 bg-danger/10"
  if (status === "caution") return "text-warn border-warn/40 bg-warn/10"
  return "text-text-muted border-border/60 bg-surface2"
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
      const payload = await tldwClient.prepareCharacterCompletion(serverChatId, {
        include_character_context: true,
        limit: 250,
        offset: 0,
        continue_as_user: resolvedSteering.continueAsUser,
        impersonate_user: resolvedSteering.impersonateUser,
        force_narrate: resolvedSteering.forceNarrate
      })
      const preparedMessages = Array.isArray(payload?.messages)
        ? payload.messages
        : []
      return buildPromptPreviewSummary(preparedMessages)
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
        <div className="border-t border-border/60 px-3 py-3 text-xs">
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
                            <td className="px-2 py-1">{section.label}</td>
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
                          {section.label}
                        </div>
                        <p className="whitespace-pre-wrap text-text">
                          {section.preview}
                        </p>
                      </div>
                    ))}

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
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
