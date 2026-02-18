import React from "react"
import { Button, Input, Skeleton, Table } from "antd"
import { Plus } from "lucide-react"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"

type DictionaryListSectionProps = {
  dictionarySearch: string
  onDictionarySearchChange: (value: string) => void
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
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Input
          value={dictionarySearch}
          onChange={(event) => onDictionarySearchChange(event.target.value)}
          allowClear
          className="sm:max-w-md"
          placeholder="Search dictionaries by name or description"
          aria-label="Search dictionaries"
        />
        <div className="flex justify-end gap-2">
          <Button onClick={onOpenImport}>Import</Button>
          <Button type="primary" icon={<Plus className="w-4 h-4" />} onClick={onOpenCreate}>
            New Dictionary
          </Button>
        </div>
      </div>
      <div className="text-xs text-text-muted">
        Processing order for active dictionaries uses Priority (alphabetical by dictionary name), then each dictionary&apos;s entry order.
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
