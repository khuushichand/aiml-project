import React from "react"
import { Dropdown, Tooltip } from "antd"
import { Copy, History, MessageCircle, MoreHorizontal, Pen, Trash2 } from "lucide-react"

type DictionaryActionsCellProps = {
  record: any
  useCompactDictionaryActions: boolean
  onOpenEdit: (record: any) => void
  onOpenEntries: (dictionaryId: number) => void
  onOpenQuickAssign: (record: any) => void
  onExportJson: (record: any) => void
  onExportMarkdown: (record: any) => void
  onOpenStats: (record: any) => void
  onOpenVersions: (record: any) => void
  onDuplicate: (record: any) => void
  onDelete: (record: any) => void
}

export const DictionaryActionsCell: React.FC<DictionaryActionsCellProps> = ({
  record,
  useCompactDictionaryActions,
  onOpenEdit,
  onOpenEntries,
  onOpenQuickAssign,
  onExportJson,
  onExportMarkdown,
  onOpenStats,
  onOpenVersions,
  onDuplicate,
  onDelete
}) => {
  return (
    <div className="flex gap-1 items-center">
      <Tooltip title="Edit dictionary">
        <button
          className="min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
          onClick={() => onOpenEdit(record)}
          aria-label={`Edit dictionary ${record.name}`}
        >
          <Pen className="w-5 h-5" />
        </button>
      </Tooltip>
      <Tooltip title="Manage entries">
        <button
          className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
          onClick={() => onOpenEntries(record.id)}
          aria-label={`Manage entries for ${record.name}`}
        >
          Entries
        </button>
      </Tooltip>
      {useCompactDictionaryActions ? (
        <Dropdown
          trigger={["click"]}
          menu={{
            items: [
              {
                key: "assign",
                label: "Quick assign to chats",
                icon: <MessageCircle className="w-4 h-4" />
              },
              { key: "json", label: "Export JSON" },
              { key: "markdown", label: "Export Markdown" },
              { key: "stats", label: "View statistics" },
              {
                key: "versions",
                label: "Version history",
                icon: <History className="w-4 h-4" />
              },
              {
                key: "duplicate",
                label: "Duplicate dictionary",
                icon: <Copy className="w-4 h-4" />
              },
              {
                key: "delete",
                danger: true,
                label: "Delete dictionary",
                icon: <Trash2 className="w-4 h-4" />
              }
            ],
            onClick: ({ key }) => {
              switch (String(key)) {
                case "assign":
                  onOpenQuickAssign(record)
                  return
                case "json":
                  onExportJson(record)
                  return
                case "markdown":
                  onExportMarkdown(record)
                  return
                case "stats":
                  onOpenStats(record)
                  return
                case "versions":
                  onOpenVersions(record)
                  return
                case "duplicate":
                  onDuplicate(record)
                  return
                case "delete":
                  onDelete(record)
                  return
                default:
                  return
              }
            }
          }}
          placement="bottomRight"
        >
          <button
            type="button"
            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
            aria-label={`More actions for ${record.name}`}
            aria-haspopup="menu"
          >
            <MoreHorizontal className="w-5 h-5" />
          </button>
        </Dropdown>
      ) : (
        <>
          <Tooltip title="Quick assign to chat sessions">
            <button
              className="min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
              onClick={() => onOpenQuickAssign(record)}
              aria-label={`Quick assign ${record.name} to chats`}
            >
              <MessageCircle className="w-5 h-5" />
            </button>
          </Tooltip>
          <Tooltip title="Export as JSON">
            <button
              className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
              onClick={() => onExportJson(record)}
              aria-label={`Export ${record.name} as JSON`}
            >
              JSON
            </button>
          </Tooltip>
          <Tooltip title="Export as Markdown">
            <button
              className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
              onClick={() => onExportMarkdown(record)}
              aria-label={`Export ${record.name} as Markdown`}
            >
              MD
            </button>
          </Tooltip>
          <Tooltip title="View statistics">
            <button
              className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
              onClick={() => onOpenStats(record)}
              aria-label={`View statistics for ${record.name}`}
            >
              Stats
            </button>
          </Tooltip>
          <Tooltip title="View version history">
            <button
              className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
              onClick={() => onOpenVersions(record)}
              aria-label={`Version history for ${record.name}`}
            >
              Versions
            </button>
          </Tooltip>
          <Tooltip title="Duplicate dictionary">
            <button
              className="min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
              onClick={() => onDuplicate(record)}
              aria-label={`Duplicate dictionary ${record.name}`}
            >
              <Copy className="w-5 h-5" />
            </button>
          </Tooltip>
          <Tooltip title="Delete dictionary">
            <button
              className="min-w-[44px] min-h-[44px] flex items-center justify-center text-danger hover:bg-danger/10 rounded-md transition-colors"
              onClick={() => onDelete(record)}
              aria-label={`Delete dictionary ${record.name}`}
            >
              <Trash2 className="w-5 h-5" />
            </button>
          </Tooltip>
        </>
      )}
    </div>
  )
}
