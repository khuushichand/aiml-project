import React from "react"
import { useTranslation } from "react-i18next"
import { Empty, Tag, Descriptions, Skeleton } from "antd"
import {
  User,
  Calendar,
  FileText,
  HardDrive,
  Tags,
  BookText
} from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { useDocumentMetadata } from "@/hooks/document-workspace"

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes?: number): string {
  if (!bytes) return "-"
  const units = ["B", "KB", "MB", "GB"]
  let unitIndex = 0
  let size = bytes
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

/**
 * Format date to localized string
 */
function formatDate(date?: Date): string {
  if (!date) return "-"
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric"
  })
}

export const DocumentInfoTab: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)

  const { data: metadata, isLoading, error } = useDocumentMetadata(activeDocumentId)

  if (!activeDocumentId) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          description={t(
            "option:documentWorkspace.noDocumentSelected",
            "No document selected"
          )}
        />
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <Skeleton active paragraph={{ rows: 1 }} />
        <Skeleton active paragraph={{ rows: 2 }} />
        <Skeleton active paragraph={{ rows: 3 }} />
      </div>
    )
  }

  if (error || !metadata) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          description={t(
            "option:documentWorkspace.errorLoadingMetadata",
            "Failed to load document info"
          )}
        />
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="space-y-4 p-4">
        {/* Title */}
        <div>
          <h3 className="mb-2 text-base font-medium text-text">
            {metadata.title}
          </h3>
        </div>

        {/* Authors */}
        {metadata.authors && metadata.authors.length > 0 && (
          <div className="flex items-start gap-2">
            <User className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
            <div className="flex flex-wrap gap-1">
              {metadata.authors.map((author, idx) => (
                <span key={idx} className="text-sm text-text">
                  {author}{idx < metadata.authors!.length - 1 ? ", " : ""}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Abstract */}
        {metadata.abstract && (
          <div>
            <div className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase text-muted">
              <BookText className="h-3.5 w-3.5" />
              {t("option:documentWorkspace.abstract", "Abstract")}
            </div>
            <p className="text-sm leading-relaxed text-text-secondary">
              {metadata.abstract}
            </p>
          </div>
        )}

        {/* Keywords */}
        {metadata.keywords && metadata.keywords.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium uppercase text-muted">
              <Tags className="h-3.5 w-3.5" />
              {t("option:documentWorkspace.keywords", "Keywords")}
            </div>
            <div className="flex flex-wrap gap-1">
              {metadata.keywords.map((keyword, idx) => (
                <Tag key={idx} className="m-0">
                  {keyword}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {/* Document Details */}
        <Descriptions
          size="small"
          column={1}
          className="[&_.ant-descriptions-item-label]:text-muted [&_.ant-descriptions-item-content]:text-text"
        >
          {metadata.fileName && (
            <Descriptions.Item
              label={
                <span className="flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5" />
                  {t("option:documentWorkspace.fileName", "File name")}
                </span>
              }
            >
              <span className="break-all">{metadata.fileName}</span>
            </Descriptions.Item>
          )}

          {metadata.creator && (
            <Descriptions.Item
              label={
                <span className="flex items-center gap-1.5">
                  <User className="h-3.5 w-3.5" />
                  {t("option:documentWorkspace.creator", "Creator")}
                </span>
              }
            >
              {metadata.creator}
            </Descriptions.Item>
          )}

          {metadata.producer && (
            <Descriptions.Item
              label={
                <span className="flex items-center gap-1.5">
                  <User className="h-3.5 w-3.5" />
                  {t("option:documentWorkspace.producer", "Producer")}
                </span>
              }
            >
              {metadata.producer}
            </Descriptions.Item>
          )}

          {metadata.pageCount !== undefined && (
            <Descriptions.Item
              label={
                <span className="flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5" />
                  {t("option:documentWorkspace.pages", "Pages")}
                </span>
              }
            >
              {metadata.pageCount}
            </Descriptions.Item>
          )}

          {metadata.fileSize !== undefined && (
            <Descriptions.Item
              label={
                <span className="flex items-center gap-1.5">
                  <HardDrive className="h-3.5 w-3.5" />
                  {t("option:documentWorkspace.fileSize", "Size")}
                </span>
              }
            >
              {formatFileSize(metadata.fileSize)}
            </Descriptions.Item>
          )}

          <Descriptions.Item
            label={
              <span className="flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                {t("option:documentWorkspace.created", "Created")}
              </span>
            }
          >
            {formatDate(metadata.createdDate)}
          </Descriptions.Item>

          {metadata.modifiedDate && (
            <Descriptions.Item
              label={
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" />
                  {t("option:documentWorkspace.modified", "Modified")}
                </span>
              }
            >
              {formatDate(metadata.modifiedDate)}
            </Descriptions.Item>
          )}
        </Descriptions>
      </div>
    </div>
  )
}

export default DocumentInfoTab
