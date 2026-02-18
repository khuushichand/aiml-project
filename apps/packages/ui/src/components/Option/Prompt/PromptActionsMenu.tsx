import { Dropdown, MenuProps, Tooltip } from "antd"
import {
  MoreHorizontal,
  Pen,
  MessageCircle,
  CopyIcon,
  Trash2,
  CloudUpload,
  CloudDownload,
  Unlink,
  AlertTriangle
} from "lucide-react"
import React from "react"
import { useTranslation } from "react-i18next"
import type { PromptSyncStatus } from "@/db/dexie/types"

interface PromptActionsMenuProps {
  promptId: string
  disabled?: boolean
  syncStatus?: PromptSyncStatus
  serverId?: number | null
  onEdit: () => void
  onDuplicate: () => void
  onUseInChat: () => void
  onDelete: () => void
  onPushToServer?: () => void
  onPullFromServer?: () => void
  onUnlink?: () => void
  onResolveConflict?: () => void
}

export const PromptActionsMenu: React.FC<PromptActionsMenuProps> = ({
  promptId,
  disabled = false,
  syncStatus,
  serverId,
  onEdit,
  onDuplicate,
  onUseInChat,
  onDelete,
  onPushToServer,
  onPullFromServer,
  onUnlink,
  onResolveConflict
}) => {
  const { t } = useTranslation(["settings", "common", "option"])

  const isSynced = !!serverId || syncStatus === "synced"
  const isConflict = syncStatus === "conflict"
  const canSync = !disabled && (onPushToServer || onPullFromServer)

  const syncItems: MenuProps["items"] = canSync ? [
    ...(onResolveConflict && isConflict ? [{
      key: "resolveConflict",
      label: t("managePrompts.sync.resolveConflict", {
        defaultValue: "Resolve conflict"
      }),
      icon: <AlertTriangle className="size-4" />,
      onClick: onResolveConflict
    }] : []),
    ...(onResolveConflict && isConflict ? [{ type: "divider" as const }] : []),
    // Push to server option (for local or pending prompts)
    ...(onPushToServer && !isSynced ? [{
      key: "push",
      label: t("managePrompts.sync.pushToServer", { defaultValue: "Push to Server" }),
      icon: <CloudUpload className="size-4" />,
      onClick: onPushToServer
    }] : []),
    // Pull from server (for synced prompts)
    ...(onPullFromServer && isSynced ? [{
      key: "pull",
      label: t("managePrompts.sync.pullFromServer", { defaultValue: "Pull from Server" }),
      icon: <CloudDownload className="size-4" />,
      onClick: onPullFromServer
    }] : []),
    // Unlink option (for synced prompts)
    ...(onUnlink && isSynced ? [{
      key: "unlink",
      label: t("managePrompts.sync.unlink", { defaultValue: "Unlink from Server" }),
      icon: <Unlink className="size-4" />,
      onClick: onUnlink
    }] : []),
    ...(canSync ? [{ type: "divider" as const }] : [])
  ] : []

  const overflowItems: MenuProps["items"] = [
    ...syncItems,
    {
      key: "duplicate",
      label: t("managePrompts.tooltip.duplicate", { defaultValue: "Duplicate" }),
      icon: <CopyIcon className="size-4" />,
      disabled,
      onClick: onDuplicate
    },
    {
      type: "divider"
    },
    {
      key: "delete",
      label: t("common:delete", { defaultValue: "Delete" }),
      icon: <Trash2 className="size-4" />,
      danger: true,
      disabled,
      onClick: onDelete
    }
  ]

  return (
    <div className="flex items-center gap-2">
      <Tooltip title={t("managePrompts.tooltip.edit")}>
        <button
          type="button"
          aria-label={t("managePrompts.tooltip.edit")}
          data-testid={`prompt-edit-${promptId}`}
          onClick={onEdit}
          disabled={disabled}
          className="inline-flex items-center justify-center p-1 rounded text-text-muted hover:text-text hover:bg-surface2 disabled:opacity-50 transition-colors"
        >
          <Pen className="size-4" />
        </button>
      </Tooltip>

      <Tooltip
        title={t("option:promptInsert.useInChatTooltip", {
          defaultValue: "Open chat and insert this prompt into the composer."
        })}
      >
        <button
          type="button"
          aria-label={t("option:promptInsert.useInChat", { defaultValue: "Use in chat" })}
          data-testid={`prompt-use-${promptId}`}
          onClick={onUseInChat}
          disabled={disabled}
          className="inline-flex items-center justify-center p-1 rounded text-text-muted hover:text-text hover:bg-surface2 disabled:opacity-50 transition-colors"
        >
          <MessageCircle className="size-4" />
        </button>
      </Tooltip>

      <Dropdown
        menu={{ items: overflowItems }}
        trigger={["click"]}
        placement="bottomRight"
      >
        <button
          type="button"
          aria-label={t("common:moreActions", { defaultValue: "More actions" })}
          data-testid={`prompt-more-${promptId}`}
          disabled={disabled}
          className="inline-flex items-center justify-center p-1 rounded text-text-muted hover:text-text hover:bg-surface2 disabled:opacity-50 transition-colors"
        >
          <MoreHorizontal className="size-4" />
        </button>
      </Dropdown>
    </div>
  )
}
