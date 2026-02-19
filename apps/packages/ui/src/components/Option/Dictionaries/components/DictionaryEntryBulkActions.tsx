import { AutoComplete, Button } from "antd"
import React from "react"

type DictionaryEntryBulkAction = null | "activate" | "deactivate" | "delete" | "group"

type DictionaryEntryBulkActionsProps = {
  selectedCount: number
  canEscalateSelectAllFilteredEntries: boolean
  filteredEntryCount: number
  onSelectAllFilteredEntries: () => void
  onClearSelection: () => void
  bulkEntryAction: DictionaryEntryBulkAction
  onActivate: () => void
  onDeactivate: () => void
  onSetGroup: () => void
  onDelete: () => void
  entryGroupOptions: Array<{ value: string; label: React.ReactNode }>
  bulkGroupName: string
  onBulkGroupNameChange: (value: string) => void
}

export const DictionaryEntryBulkActions: React.FC<DictionaryEntryBulkActionsProps> = ({
  selectedCount,
  canEscalateSelectAllFilteredEntries,
  filteredEntryCount,
  onSelectAllFilteredEntries,
  onClearSelection,
  bulkEntryAction,
  onActivate,
  onDeactivate,
  onSetGroup,
  onDelete,
  entryGroupOptions,
  bulkGroupName,
  onBulkGroupNameChange
}) => {
  return (
    <div className="rounded border border-border p-2 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold">{selectedCount} selected</span>
        <div className="flex flex-wrap items-center gap-2">
          {canEscalateSelectAllFilteredEntries && (
            <Button
              type="link"
              size="small"
              className="px-0"
              onClick={onSelectAllFilteredEntries}
              aria-label={`Select all ${filteredEntryCount} entries`}>
              Select all {filteredEntryCount} entries
            </Button>
          )}
          <Button
            type="link"
            size="small"
            className="px-0"
            onClick={onClearSelection}
            aria-label="Clear selected entries">
            Clear selection
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="small" loading={bulkEntryAction === "activate"} onClick={onActivate}>
          Enable
        </Button>
        <Button size="small" loading={bulkEntryAction === "deactivate"} onClick={onDeactivate}>
          Disable
        </Button>
        <AutoComplete
          options={entryGroupOptions}
          value={bulkGroupName}
          onChange={(value) => onBulkGroupNameChange(String(value || ""))}
          placeholder="Group name"
          className="min-w-[180px]"
          aria-label="Bulk group name"
          filterOption={(inputValue, option) =>
            String(option?.value || "")
              .toLowerCase()
              .includes(inputValue.toLowerCase())
          }
        />
        <Button size="small" loading={bulkEntryAction === "group"} onClick={onSetGroup}>
          Set Group
        </Button>
        <Button size="small" danger loading={bulkEntryAction === "delete"} onClick={onDelete}>
          Delete
        </Button>
      </div>
    </div>
  )
}
