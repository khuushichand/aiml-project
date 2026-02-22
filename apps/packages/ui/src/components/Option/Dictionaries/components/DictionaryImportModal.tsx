import React from "react"
import { Button, Descriptions, Input, Modal, Select } from "antd"

type DictionaryImportFormat = "json" | "markdown"
type DictionaryImportMode = "file" | "paste"

type DictionaryImportPreview = {
  format: DictionaryImportFormat
  payload:
    | { kind: "json"; data: any }
    | { kind: "markdown"; name: string; content: string }
  summary: {
    name: string
    entryCount: number
    groups: string[]
    hasAdvancedFields: boolean
  }
}

type DictionaryImportConflictResolution = {
  preview: DictionaryImportPreview
  suggestedName: string
} | null

type DictionaryImportModalProps = {
  open: boolean
  onCancel: () => void
  importFormat: DictionaryImportFormat
  onImportFormatChange: (value: DictionaryImportFormat) => void
  importMode: DictionaryImportMode
  onImportModeChange: (value: DictionaryImportMode) => void
  importSourceContent: string
  onImportSourceContentChange: (value: string) => void
  importMarkdownName: string
  onImportMarkdownNameChange: (value: string) => void
  importFileName: string | null
  onImportFileSelection: (event: React.ChangeEvent<HTMLInputElement>) => void
  activateOnImport: boolean
  onActivateOnImportChange: (value: boolean) => void
  onBuildImportPreview: () => void
  importValidationErrors: string[]
  importPreview: DictionaryImportPreview | null
  onConfirmImport: () => void
  importing: boolean
  importConflictResolution: DictionaryImportConflictResolution
  onCloseConflictResolution: () => void
  onResolveConflictRename: () => void
  onResolveConflictReplace: () => void
}

export const DictionaryImportModal: React.FC<DictionaryImportModalProps> = ({
  open,
  onCancel,
  importFormat,
  onImportFormatChange,
  importMode,
  onImportModeChange,
  importSourceContent,
  onImportSourceContentChange,
  importMarkdownName,
  onImportMarkdownNameChange,
  importFileName,
  onImportFileSelection,
  activateOnImport,
  onActivateOnImportChange,
  onBuildImportPreview,
  importValidationErrors,
  importPreview,
  onConfirmImport,
  importing,
  importConflictResolution,
  onCloseConflictResolution,
  onResolveConflictRename,
  onResolveConflictReplace
}) => {
  return (
    <>
      <Modal title="Import Dictionary" open={open} onCancel={onCancel} footer={null}>
        <div className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="space-y-1">
              <div className="text-xs font-medium text-text">Format</div>
              <Select
                value={importFormat}
                onChange={(value) =>
                  onImportFormatChange(value as DictionaryImportFormat)
                }
                options={[
                  { label: "JSON (full fidelity)", value: "json" },
                  { label: "Markdown", value: "markdown" }
                ]}
              />
            </div>
            <div className="space-y-1">
              <div className="text-xs font-medium text-text">Source</div>
              <Select
                value={importMode}
                onChange={(value) => onImportModeChange(value as DictionaryImportMode)}
                options={[
                  { label: "File upload", value: "file" },
                  { label: "Paste content", value: "paste" }
                ]}
              />
            </div>
          </div>

          {importMode === "file" ? (
            <div className="space-y-2">
              <input
                type="file"
                accept={
                  importFormat === "markdown"
                    ? ".md,.markdown,text/markdown,text/plain"
                    : "application/json,.json"
                }
                onChange={onImportFileSelection}
              />
              {importFileName && (
                <p className="text-xs text-text-muted">Selected: {importFileName}</p>
              )}
            </div>
          ) : (
            <Input.TextArea
              rows={6}
              value={importSourceContent}
              onChange={(event) => onImportSourceContentChange(event.target.value)}
              placeholder={
                importFormat === "markdown"
                  ? "Paste markdown dictionary content..."
                  : "Paste JSON dictionary content..."
              }
            />
          )}

          {importFormat === "markdown" && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-text">Dictionary name</div>
              <Input
                value={importMarkdownName}
                onChange={(event) => onImportMarkdownNameChange(event.target.value)}
                placeholder="Optional (defaults to markdown heading or file name)"
              />
            </div>
          )}

          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={activateOnImport}
              onChange={(event) => onActivateOnImportChange(event.target.checked)}
            />{" "}
            Activate after import
          </label>
          <Button onClick={onBuildImportPreview} disabled={!importSourceContent.trim()}>
            Preview import
          </Button>
          {importValidationErrors.length > 0 && (
            <div className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2">
              <p className="text-sm font-medium text-danger">
                Unable to import this file. Fix the following and retry:
              </p>
              <ul className="mt-1 list-disc pl-4 text-xs text-danger/90 space-y-1">
                {importValidationErrors.map((issue, index) => (
                  <li key={`${issue}-${index}`}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {importPreview && (
            <div className="space-y-2 rounded-md border border-border bg-surface2/40 px-3 py-2">
              <div className="text-sm font-medium text-text">Import preview</div>
              <Descriptions size="small" bordered column={1}>
                <Descriptions.Item label="Format">
                  {importPreview.format === "json" ? "JSON" : "Markdown"}
                </Descriptions.Item>
                <Descriptions.Item label="Dictionary name">
                  {importPreview.summary.name}
                </Descriptions.Item>
                <Descriptions.Item label="Entries">
                  {importPreview.summary.entryCount}
                </Descriptions.Item>
                <Descriptions.Item label="Groups">
                  {importPreview.summary.groups.length > 0
                    ? importPreview.summary.groups.join(", ")
                    : "—"}
                </Descriptions.Item>
                <Descriptions.Item label="Advanced fields">
                  {importPreview.summary.hasAdvancedFields ? "Detected" : "Not detected"}
                </Descriptions.Item>
              </Descriptions>
              <Button type="primary" onClick={onConfirmImport} loading={importing}>
                Confirm import
              </Button>
            </div>
          )}
          {importing && (
            <p className="text-xs text-text-muted">Importing dictionary...</p>
          )}
        </div>
      </Modal>

      <Modal
        title="Dictionary name conflict"
        open={!!importConflictResolution}
        onCancel={onCloseConflictResolution}
        footer={null}
      >
        {importConflictResolution && (
          <div className="space-y-3">
            <p className="text-sm text-text">
              A dictionary named{" "}
              <span className="font-medium">
                {importConflictResolution.preview.summary.name}
              </span>{" "}
              already exists.
            </p>
            <div className="space-y-2">
              <Button
                type="primary"
                onClick={onResolveConflictRename}
                loading={importing}
                block
              >
                Rename to "{importConflictResolution.suggestedName}"
              </Button>
              <Button
                danger
                onClick={onResolveConflictReplace}
                loading={importing}
                block
              >
                Replace existing
              </Button>
              <Button onClick={onCloseConflictResolution} block>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  )
}
