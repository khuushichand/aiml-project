import React, { useState } from "react"
import { useTranslation } from "react-i18next"
import { Modal, Radio, Button, message } from "antd"
import type { RadioChangeEvent } from "antd"
import { FileText, FileJson, File } from "lucide-react"
import type { Annotation, DocumentType } from "../types"
import {
  downloadAnnotations,
  type ExportFormat
} from "../utils/annotationExport"

interface ExportAnnotationsModalProps {
  open: boolean
  onClose: () => void
  annotations: Annotation[]
  documentTitle: string
  documentType: DocumentType | null
}

const FORMAT_OPTIONS: Array<{
  value: ExportFormat
  label: string
  description: string
  icon: React.ReactNode
}> = [
  {
    value: "markdown",
    label: "Markdown",
    description: "Formatted text with headings and quotes",
    icon: <FileText className="h-5 w-5" />
  },
  {
    value: "json",
    label: "JSON",
    description: "Structured data for programmatic use",
    icon: <FileJson className="h-5 w-5" />
  },
  {
    value: "text",
    label: "Plain Text",
    description: "Simple text format",
    icon: <File className="h-5 w-5" />
  }
]

/**
 * Modal for selecting annotation export format and triggering download.
 */
export const ExportAnnotationsModal: React.FC<ExportAnnotationsModalProps> = ({
  open,
  onClose,
  annotations,
  documentTitle,
  documentType
}) => {
  const { t } = useTranslation(["option", "common"])
  const [format, setFormat] = useState<ExportFormat>("markdown")

  const handleFormatChange = (e: RadioChangeEvent) => {
    setFormat(e.target.value)
  }

  const handleExport = () => {
    try {
      downloadAnnotations(annotations, documentTitle, documentType, format)
      message.success(
        t("option:documentWorkspace.exportSuccess", "Annotations exported successfully")
      )
      onClose()
    } catch (err) {
      message.error(
        t("option:documentWorkspace.exportFailed", "Failed to export annotations")
      )
    }
  }

  return (
    <Modal
      title={t("option:documentWorkspace.exportAnnotations", "Export Annotations")}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          {t("common:cancel", "Cancel")}
        </Button>,
        <Button
          key="export"
          type="primary"
          onClick={handleExport}
          disabled={annotations.length === 0}
        >
          {t("option:documentWorkspace.export", "Export")}
        </Button>
      ]}
      width={420}
    >
      <div className="space-y-4">
        {/* Annotation count */}
        <div className="rounded-lg border border-border bg-surface-hover p-3">
          <p className="text-sm">
            <span className="font-medium">{annotations.length}</span>{" "}
            {t("option:documentWorkspace.annotationsToExport", "annotations to export")}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {documentTitle}
          </p>
        </div>

        {/* Format selection */}
        <div>
          <p className="mb-2 text-sm font-medium">
            {t("option:documentWorkspace.selectFormat", "Select format")}
          </p>
          <Radio.Group
            value={format}
            onChange={handleFormatChange}
            className="w-full"
          >
            <div className="space-y-2">
              {FORMAT_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                    format === option.value
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50"
                  }`}
                >
                  <Radio value={option.value} className="mt-0.5" />
                  <div className="flex items-start gap-3">
                    <span className="text-text-secondary">{option.icon}</span>
                    <div>
                      <p className="font-medium">{option.label}</p>
                      <p className="text-xs text-text-secondary">
                        {option.description}
                      </p>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </Radio.Group>
        </div>

        {/* Empty state warning */}
        {annotations.length === 0 && (
          <div className="rounded border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
            {t(
              "option:documentWorkspace.noAnnotationsToExport",
              "No annotations to export. Add some highlights or notes first."
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}

export default ExportAnnotationsModal
