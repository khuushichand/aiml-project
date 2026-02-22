import React from "react"
import { Tooltip } from "antd"
import { AlertCircle, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"

type DictionaryValidationStatus = {
  status: "valid" | "warning" | "error" | "loading" | "unknown"
  message?: string
}

type DictionaryValidationStatusCellProps = {
  record: any
  status: DictionaryValidationStatus | undefined
  onValidate: (dictionaryId: number) => void
}

export const DictionaryValidationStatusCell: React.FC<
  DictionaryValidationStatusCellProps
> = ({ record, status, onValidate }) => {
  if (!status) {
    return (
      <Tooltip title="Click to validate">
        <button
          className="min-w-[36px] min-h-[36px] px-2 inline-flex items-center gap-1 text-xs text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
          onClick={() => onValidate(record.id)}
          aria-label={`Validate dictionary ${record.name}`}
        >
          <CheckCircle2 className="w-4 h-4 opacity-40" />
          <span>Check</span>
        </button>
      </Tooltip>
    )
  }

  if (status.status === "loading") {
    return (
      <Tooltip title="Validating...">
        <span className="inline-flex items-center gap-1 text-xs text-text-muted">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Checking</span>
        </span>
      </Tooltip>
    )
  }

  if (status.status === "valid") {
    return (
      <Tooltip title={status.message || "Valid"}>
        <button
          className="min-w-[36px] min-h-[36px] px-2 inline-flex items-center gap-1 text-xs text-text hover:bg-success/10 rounded-md transition-colors"
          onClick={() => onValidate(record.id)}
          aria-label={`Dictionary ${record.name} is valid. Click to re-validate.`}
        >
          <CheckCircle2 className="w-4 h-4 text-success" />
          <span>Valid</span>
        </button>
      </Tooltip>
    )
  }

  if (status.status === "warning") {
    return (
      <Tooltip title={status.message || "Has warnings"}>
        <button
          className="min-w-[36px] min-h-[36px] px-2 inline-flex items-center gap-1 text-xs text-text hover:bg-warn/10 rounded-md transition-colors"
          onClick={() => onValidate(record.id)}
          aria-label={`Dictionary ${record.name} has warnings. Click to re-validate.`}
        >
          <AlertTriangle className="w-4 h-4 text-warn" />
          <span>Warn</span>
        </button>
      </Tooltip>
    )
  }

  return (
    <Tooltip title={status.message || "Has errors"}>
      <button
        className="min-w-[36px] min-h-[36px] px-2 inline-flex items-center gap-1 text-xs text-text hover:bg-danger/10 rounded-md transition-colors"
        onClick={() => onValidate(record.id)}
        aria-label={`Dictionary ${record.name} has errors. Click to re-validate.`}
      >
        <AlertCircle className="w-4 h-4 text-danger" />
        <span>Error</span>
      </button>
    </Tooltip>
  )
}
