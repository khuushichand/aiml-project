import React, { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Empty, Popconfirm, Tooltip } from "antd"
import { Plus, Server, Trash2, Edit2, Globe, Terminal } from "lucide-react"
import type { ACPMCPServerConfig } from "@/services/acp/types"
import { MCPServerConfigForm } from "./MCPServerConfigForm"

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface MCPServerConfigListProps {
  servers: ACPMCPServerConfig[]
  onChange: (servers: ACPMCPServerConfig[]) => void
  disabled?: boolean
}

// -----------------------------------------------------------------------------
// Server Item Component
// -----------------------------------------------------------------------------

interface ServerItemProps {
  server: ACPMCPServerConfig
  onEdit: () => void
  onDelete: () => void
  disabled?: boolean
}

const ServerItem: React.FC<ServerItemProps> = ({
  server,
  onEdit,
  onDelete,
  disabled,
}) => {
  const { t } = useTranslation("playground")

  const Icon = server.type === "websocket" ? Globe : Terminal

  return (
    <div className="group flex items-center gap-3 rounded-lg border border-border bg-surface2/50 p-2 transition-colors hover:bg-surface2">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-surface2">
        <Icon className="h-4 w-4 text-text-muted" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-text">{server.name}</span>
          <span className="shrink-0 rounded bg-surface2 px-1.5 py-0.5 text-xs text-text-muted">
            {server.type}
          </span>
        </div>
        <p className="truncate text-xs text-text-muted">
          {server.type === "websocket" ? server.url : server.command}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <Tooltip title={t("acp.mcp.edit", "Edit")}>
          <Button
            type="text"
            size="small"
            icon={<Edit2 className="h-3.5 w-3.5" />}
            onClick={onEdit}
            disabled={disabled}
          />
        </Tooltip>
        <Popconfirm
          title={t("acp.mcp.deleteConfirm", "Remove this server?")}
          onConfirm={onDelete}
          okText={t("common:yes", "Yes")}
          cancelText={t("common:no", "No")}
          disabled={disabled}
        >
          <Tooltip title={t("acp.mcp.delete", "Remove")}>
            <Button
              type="text"
              size="small"
              icon={<Trash2 className="h-3.5 w-3.5" />}
              className="hover:text-error"
              disabled={disabled}
            />
          </Tooltip>
        </Popconfirm>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------------
// Main Component
// -----------------------------------------------------------------------------

export const MCPServerConfigList: React.FC<MCPServerConfigListProps> = ({
  servers,
  onChange,
  disabled,
}) => {
  const { t } = useTranslation("playground")
  const [showForm, setShowForm] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  const handleAdd = () => {
    setEditingIndex(null)
    setShowForm(true)
  }

  const handleEdit = (index: number) => {
    setEditingIndex(index)
    setShowForm(true)
  }

  const handleDelete = (index: number) => {
    const newServers = [...servers]
    newServers.splice(index, 1)
    onChange(newServers)
  }

  const handleFormSave = (server: ACPMCPServerConfig) => {
    if (editingIndex !== null) {
      // Editing existing server
      const newServers = [...servers]
      newServers[editingIndex] = server
      onChange(newServers)
    } else {
      // Adding new server
      onChange([...servers, server])
    }
    setShowForm(false)
    setEditingIndex(null)
  }

  const handleFormCancel = () => {
    setShowForm(false)
    setEditingIndex(null)
  }

  if (showForm) {
    return (
      <MCPServerConfigForm
        server={editingIndex !== null ? servers[editingIndex] : undefined}
        onSave={handleFormSave}
        onCancel={handleFormCancel}
      />
    )
  }

  return (
    <div className="space-y-2">
      {servers.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={t("acp.mcp.noServers", "No MCP servers configured")}
          className="py-4"
        >
          <Button
            type="dashed"
            icon={<Plus className="h-4 w-4" />}
            onClick={handleAdd}
            disabled={disabled}
          >
            {t("acp.mcp.addServer", "Add Server")}
          </Button>
        </Empty>
      ) : (
        <>
          {servers.map((server, index) => (
            <ServerItem
              key={`${server.name}-${index}`}
              server={server}
              onEdit={() => handleEdit(index)}
              onDelete={() => handleDelete(index)}
              disabled={disabled}
            />
          ))}
          <Button
            type="dashed"
            icon={<Plus className="h-4 w-4" />}
            onClick={handleAdd}
            disabled={disabled}
            className="w-full"
          >
            {t("acp.mcp.addAnother", "Add Another Server")}
          </Button>
        </>
      )}
    </div>
  )
}

export default MCPServerConfigList
