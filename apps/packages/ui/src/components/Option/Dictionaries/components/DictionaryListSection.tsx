import React from "react"
import { Button, Input, Select, Skeleton, Table } from "antd"
import { ChevronDown, ChevronUp, Plus } from "lucide-react"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"

const HowItWorksDictionaries: React.FC = () => {
  const [expanded, setExpanded] = React.useState(true)
  return (
    <div className="mb-4 rounded-lg border border-border bg-surface p-4">
      <button
        type="button"
        className="flex w-full items-center justify-between text-sm font-medium text-text"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        How it works
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {expanded && (
        <ol className="mt-3 list-inside list-decimal space-y-2 text-xs text-text-muted">
          <li>
            <span className="font-medium text-text">Create a dictionary</span>{" "}
            — a set of find-and-replace rules (or start from a template).
          </li>
          <li>
            <span className="font-medium text-text">Add entries</span>{" "}
            — each entry has a pattern to find and text to replace it with.
          </li>
          <li>
            <span className="font-medium text-text">Test with preview</span>{" "}
            — paste sample text to see the rules in action before going live.
          </li>
          <li>
            <span className="font-medium text-text">Assign to chats</span>{" "}
            — link the dictionary to chat sessions so rules apply automatically.
          </li>
        </ol>
      )}
    </div>
  )
}

type DictionaryListSectionProps = {
  dictionarySearch: string
  onDictionarySearchChange: (value: string) => void
  categoryFilter: string
  onCategoryFilterChange: (value: string) => void
  tagFilters: string[]
  onTagFiltersChange: (value: string[]) => void
  categoryFilterOptions: string[]
  tagFilterOptions: string[]
  onOpenImport: () => void
  onOpenCreate: () => void
  status: "pending" | "success" | "error" | string
  dictionariesUnsupported: boolean
  unsupportedTitle: string
  unsupportedDescription: string
  unsupportedPrimaryActionLabel: string
  onOpenHealthDiagnostics: () => void
  data: any[] | undefined
  filteredDictionaries: any[]
  columns: any[]
  error: unknown
  onRetry: () => void
}

export const DictionaryListSection: React.FC<DictionaryListSectionProps> = ({
  dictionarySearch,
  onDictionarySearchChange,
  categoryFilter,
  onCategoryFilterChange,
  tagFilters,
  onTagFiltersChange,
  categoryFilterOptions,
  tagFilterOptions,
  onOpenImport,
  onOpenCreate,
  status,
  dictionariesUnsupported,
  unsupportedTitle,
  unsupportedDescription,
  unsupportedPrimaryActionLabel,
  onOpenHealthDiagnostics,
  data,
  filteredDictionaries,
  columns,
  error,
  onRetry
}) => {
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={dictionarySearch}
            onChange={(event) => onDictionarySearchChange(event.target.value)}
            allowClear
            className="w-full min-w-[220px] md:w-72"
            placeholder="Search dictionaries by name, description, category, or tags"
            aria-label="Search dictionaries"
          />
          <Select
            allowClear
            value={categoryFilter || undefined}
            onChange={(value) => onCategoryFilterChange(value || "")}
            options={categoryFilterOptions.map((category) => ({
              label: category,
              value: category,
            }))}
            placeholder="All categories"
            className="w-40"
            aria-label="Filter dictionaries by category"
          />
          <Select
            mode="multiple"
            allowClear
            value={tagFilters}
            onChange={(value) => onTagFiltersChange(value)}
            options={tagFilterOptions.map((tag) => ({
              label: tag,
              value: tag,
            }))}
            placeholder="Filter by tags"
            className="w-44"
            maxTagCount="responsive"
            aria-label="Filter dictionaries by tags"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={onOpenImport}>Import</Button>
          <Button type="primary" icon={<Plus className="w-4 h-4" />} onClick={onOpenCreate}>
            New Dictionary
          </Button>
        </div>
      </div>
      <div className="rounded border border-border bg-surface-secondary px-3 py-2">
        <p className="text-xs text-text-muted">
          Processing order for active dictionaries uses Priority (alphabetical by dictionary name), then each dictionary&apos;s entry order.
        </p>
      </div>
      {status === "pending" && <Skeleton active paragraph={{ rows: 6 }} />}
      {status === "success" && dictionariesUnsupported && (
        <FeatureEmptyState
          title={unsupportedTitle}
          description={unsupportedDescription}
          primaryActionLabel={unsupportedPrimaryActionLabel}
          onPrimaryAction={onOpenHealthDiagnostics}
        />
      )}
      {status === "success" && !dictionariesUnsupported && (
        Array.isArray(data) && data.length === 0 ? (
          <>
          <HowItWorksDictionaries />
          <FeatureEmptyState
            title="No dictionaries yet"
            description="Create your first dictionary to transform text consistently across chats."
            examples={[
              "Medical abbreviations (e.g., BP -> blood pressure)",
              "Custom terminology (e.g., internal product names)",
              "Roleplay language style mappings"
            ]}
            primaryActionLabel="Create your first dictionary"
            onPrimaryAction={onOpenCreate}
            secondaryActionLabel="Import dictionary"
            onSecondaryAction={onOpenImport}
          />
          </>
        ) : (
          <Table
            rowKey={(record: any) => record.id}
            dataSource={filteredDictionaries}
            columns={columns as any}
            pagination={{
              pageSize: 20,
              showSizeChanger: true,
              pageSizeOptions: [10, 20, 50, 100],
              showTotal: (total, range) => `${range[0]}-${range[1]} of ${total}`
            }}
          />
        )
      )}
      {status === "error" && !dictionariesUnsupported && (
        <FeatureEmptyState
          title="Unable to load dictionaries"
          description={
            error instanceof Error
              ? `Could not load dictionaries: ${error.message}`
              : "Could not load dictionaries right now. Check your server connection and try again."
          }
          primaryActionLabel="Retry"
          onPrimaryAction={onRetry}
          secondaryActionLabel="Import dictionary"
          onSecondaryAction={onOpenImport}
        />
      )}
    </>
  )
}
