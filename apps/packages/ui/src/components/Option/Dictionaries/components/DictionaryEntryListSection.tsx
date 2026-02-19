import React from "react"
import { Input, Select, Skeleton, Table } from "antd"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { DictionaryEntryBulkActions } from "./DictionaryEntryBulkActions"
import { toSafeNonNegativeInteger } from "./dictionaryEntryUtils"

type DictionaryEntryBulkAction =
  | null
  | "activate"
  | "deactivate"
  | "delete"
  | "group"

type DictionaryEntryListSectionProps = {
  entrySearch: string
  onEntrySearchChange: (value: string) => void
  entryGroupFilter?: string
  onEntryGroupFilterChange: (value: string | undefined) => void
  entryGroupOptions: Array<{ label: string; value: string }>
  entriesStatus: "pending" | "success" | "error" | string
  hasAnyEntries: boolean
  canReorderEntries: boolean
  selectedEntryIds: number[]
  canEscalateSelectAllFilteredEntries: boolean
  filteredEntryIds: number[]
  onSelectAllFilteredEntries: () => void
  onClearSelection: () => void
  bulkEntryAction: DictionaryEntryBulkAction
  onActivate: () => void
  onDeactivate: () => void
  onSetGroup: () => void
  onDelete: () => void
  bulkGroupName: string
  onBulkGroupNameChange: (value: string) => void
  entriesError: unknown
  onRetryEntries: () => void
  onAddFirstEntry: () => void
  filteredEntries: any[]
  highlightedValidationEntryId: number | null
  selectedEntryRowKeys: React.Key[]
  onSelectionChange: (keys: React.Key[]) => void
  normalizedEntryGroupFilter?: string
  entryTableColumns: any[]
}

export const DictionaryEntryListSection: React.FC<DictionaryEntryListSectionProps> = ({
  entrySearch,
  onEntrySearchChange,
  entryGroupFilter,
  onEntryGroupFilterChange,
  entryGroupOptions,
  entriesStatus,
  hasAnyEntries,
  canReorderEntries,
  selectedEntryIds,
  canEscalateSelectAllFilteredEntries,
  filteredEntryIds,
  onSelectAllFilteredEntries,
  onClearSelection,
  bulkEntryAction,
  onActivate,
  onDeactivate,
  onSetGroup,
  onDelete,
  bulkGroupName,
  onBulkGroupNameChange,
  entriesError,
  onRetryEntries,
  onAddFirstEntry,
  filteredEntries,
  highlightedValidationEntryId,
  selectedEntryRowKeys,
  onSelectionChange,
  normalizedEntryGroupFilter,
  entryTableColumns,
}) => {
  return (
    <>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Input
          value={entrySearch}
          onChange={(event) => onEntrySearchChange(event.target.value)}
          allowClear
          className="sm:max-w-md"
          placeholder="Search entries by pattern, replacement, or group"
          aria-label="Search dictionary entries"
        />
        <Select
          allowClear
          value={entryGroupFilter}
          onChange={(value) =>
            onEntryGroupFilterChange(
              typeof value === "string" && value.trim() ? value : undefined
            )
          }
          placeholder="All groups"
          options={entryGroupOptions}
          className="sm:w-56"
          aria-label="Filter entries by group"
        />
      </div>
      {entriesStatus === "success" && hasAnyEntries && (
        <div className="space-y-2">
          <p className="text-xs text-text-muted">
            {canReorderEntries
              ? "Entries are processed in priority order (top to bottom). Use the up/down controls to reorder."
              : "Entries are processed in priority order. Clear search/group filters to reorder."}
          </p>
          {selectedEntryIds.length > 0 && (
            <DictionaryEntryBulkActions
              selectedCount={selectedEntryIds.length}
              canEscalateSelectAllFilteredEntries={canEscalateSelectAllFilteredEntries}
              filteredEntryCount={filteredEntryIds.length}
              onSelectAllFilteredEntries={onSelectAllFilteredEntries}
              onClearSelection={onClearSelection}
              bulkEntryAction={bulkEntryAction}
              onActivate={onActivate}
              onDeactivate={onDeactivate}
              onSetGroup={onSetGroup}
              onDelete={onDelete}
              entryGroupOptions={entryGroupOptions}
              bulkGroupName={bulkGroupName}
              onBulkGroupNameChange={onBulkGroupNameChange}
            />
          )}
        </div>
      )}

      {entriesStatus === "pending" && <Skeleton active paragraph={{ rows: 4 }} />}
      {entriesStatus === "error" && (
        <FeatureEmptyState
          title="Unable to load entries"
          description={
            entriesError instanceof Error
              ? `Could not load entries: ${entriesError.message}`
              : "Could not load entries right now. Please retry."
          }
          primaryActionLabel="Retry"
          onPrimaryAction={onRetryEntries}
        />
      )}
      {entriesStatus === "success" && (
        !hasAnyEntries ? (
          <FeatureEmptyState
            title="No entries yet"
            description="Add a pattern/replacement pair to start transforming text."
            examples={[
              "Literal: BP -> blood pressure",
              "Regex: /Dr\\./ -> Doctor",
              "Group entries to organize related substitutions",
            ]}
            primaryActionLabel="Add first entry"
            onPrimaryAction={onAddFirstEntry}
          />
        ) : (
          <Table
            size="small"
            rowKey={(entryRecord: any) => entryRecord.id}
            dataSource={filteredEntries}
            rowClassName={(entryRecord: any) => {
              if (Number(entryRecord?.id) === highlightedValidationEntryId) {
                return "bg-warn/10"
              }
              return toSafeNonNegativeInteger(entryRecord?.usage_count) === 0
                ? "bg-surface2/40"
                : ""
            }}
            rowSelection={{
              selectedRowKeys: selectedEntryRowKeys,
              onChange: onSelectionChange,
              preserveSelectedRowKeys: true,
            }}
            locale={{
              emptyText:
                entrySearch.trim() || normalizedEntryGroupFilter
                  ? "No entries match the current filters."
                  : "No entries available.",
            }}
            columns={entryTableColumns as any}
          />
        )
      )}
    </>
  )
}
