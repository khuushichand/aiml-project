import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Drawer, Timeline, Skeleton, notification, Tag, Empty } from "antd"
import { History, Undo2, CheckCircle2 } from "lucide-react"
import React from "react"
import { useTranslation } from "react-i18next"
import {
  getPromptHistory,
  revertPrompt,
  getPrompt,
  type PromptVersion
} from "@/services/prompt-studio"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { Button } from "@/components/Common/Button"
import { usePromptStudioStore } from "@/store/prompt-studio"

type VersionHistoryDrawerProps = {
  open: boolean
  promptId: number | null
  onClose: () => void
}

export const VersionHistoryDrawer: React.FC<VersionHistoryDrawerProps> = ({
  open,
  promptId,
  onClose
}) => {
  const { t } = useTranslation(["settings", "common"])
  const queryClient = useQueryClient()
  const confirmDanger = useConfirmDanger()

  const selectedProjectId = usePromptStudioStore((s) => s.selectedProjectId)

  // Fetch current prompt to know current version
  const { data: promptResponse } = useQuery({
    queryKey: ["prompt-studio", "prompt", promptId],
    queryFn: () => getPrompt(promptId!),
    enabled: open && promptId !== null
  })

  const currentPrompt = (promptResponse as any)?.data?.data
  const currentVersion = currentPrompt?.version_number

  // Fetch version history
  const { data: historyResponse, status: historyStatus } = useQuery({
    queryKey: ["prompt-studio", "prompt-history", promptId],
    queryFn: () => getPromptHistory(promptId!),
    enabled: open && promptId !== null
  })

  const versions: PromptVersion[] = (historyResponse as any)?.data?.data ?? []

  // Revert mutation
  const revertMutation = useMutation({
    mutationFn: (version: number) => revertPrompt(promptId!, version),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["prompt-studio", "prompts", selectedProjectId]
      })
      queryClient.invalidateQueries({
        queryKey: ["prompt-studio", "prompt", promptId]
      })
      queryClient.invalidateQueries({
        queryKey: ["prompt-studio", "prompt-history", promptId]
      })
      notification.success({
        message: t("managePrompts.studio.prompts.revertSuccess", {
          defaultValue: "Prompt reverted"
        }),
        description: t("managePrompts.studio.prompts.revertSuccessDesc", {
          defaultValue: "A new version has been created from the selected version."
        })
      })
    },
    onError: (error: any) => {
      notification.error({
        message: t("common:error", { defaultValue: "Error" }),
        description: error?.message || t("common:unknownError")
      })
    }
  })

  const handleRevert = async (version: PromptVersion) => {
    const ok = await confirmDanger({
      title: t("managePrompts.studio.prompts.revertConfirmTitle", {
        defaultValue: "Revert to version {{version}}?",
        version: version.version_number
      }),
      content: t("managePrompts.studio.prompts.revertConfirmContent", {
        defaultValue:
          "This will create a new version with the content from version {{version}}. The current version will be preserved in history.",
        version: version.version_number
      }),
      okText: t("managePrompts.studio.prompts.revertBtn", {
        defaultValue: "Revert"
      }),
      cancelText: t("common:cancel", { defaultValue: "Cancel" })
    })

    if (ok) {
      revertMutation.mutate(version.version_number)
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "-"
    return new Date(dateStr).toLocaleString()
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          <History className="size-5" />
          {t("managePrompts.studio.prompts.versionHistoryTitle", {
            defaultValue: "Version History"
          })}
        </span>
      }
      width={480}
      destroyOnHidden
    >
      {historyStatus === "pending" && <Skeleton paragraph={{ rows: 6 }} />}

      {historyStatus === "success" && versions.length === 0 && (
        <Empty
          description={t("managePrompts.studio.prompts.noVersionHistory", {
            defaultValue: "No version history available"
          })}
        />
      )}

      {historyStatus === "success" && versions.length > 0 && (
        <Timeline
          items={versions
            .sort((a, b) => b.version_number - a.version_number)
            .map((version) => {
              const isCurrent = version.version_number === currentVersion
              return {
                color: isCurrent ? "green" : "gray",
                dot: isCurrent ? (
                  <CheckCircle2 className="size-4 text-success" />
                ) : undefined,
                children: (
                  <div
                    className={`p-3 rounded-md border ${
                      isCurrent
                        ? "border-success/30 bg-success/5"
                        : "border-border bg-surface2/50"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Tag color={isCurrent ? "green" : "default"}>
                          v{version.version_number}
                        </Tag>
                        {isCurrent && (
                          <span className="text-xs text-success font-medium">
                            {t("managePrompts.studio.prompts.currentVersion", {
                              defaultValue: "Current"
                            })}
                          </span>
                        )}
                      </div>
                      {!isCurrent && (
                        <Button
                          type="ghost"
                          size="sm"
                          onClick={() => handleRevert(version)}
                          loading={revertMutation.isPending}
                        >
                          <Undo2 className="size-3 mr-1" />
                          {t("managePrompts.studio.prompts.revertBtn", {
                            defaultValue: "Revert"
                          })}
                        </Button>
                      )}
                    </div>

                    <div className="space-y-1">
                      <p className="text-sm font-medium">{version.name}</p>
                      {version.change_description && (
                        <p className="text-sm text-text-muted">
                          {version.change_description}
                        </p>
                      )}
                      <p className="text-xs text-text-muted">
                        {formatDate(version.created_at)}
                      </p>
                    </div>
                  </div>
                )
              }
            })}
        />
      )}
    </Drawer>
  )
}
