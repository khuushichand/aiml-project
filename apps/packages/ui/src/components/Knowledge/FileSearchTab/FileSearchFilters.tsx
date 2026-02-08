import React from "react"
import { Select } from "antd"
import { useTranslation } from "react-i18next"
import type { FileSearchMediaType } from "../hooks/useFileSearch"
import { FILE_SEARCH_MEDIA_TYPES } from "../hooks/useFileSearch"
import type { SortMode } from "../hooks"

type FileSearchFiltersProps = {
  mediaTypes: FileSearchMediaType[]
  onMediaTypesChange: (types: FileSearchMediaType[]) => void
  sortMode: SortMode
  onSortModeChange: (mode: SortMode) => void
  disabled?: boolean
}

const MEDIA_TYPE_I18N_KEYS: Record<FileSearchMediaType, [string, string]> = {
  video: ["sidepanel:fileSearch.mediaType.video", "Video"],
  audio: ["sidepanel:fileSearch.mediaType.audio", "Audio"],
  pdf: ["sidepanel:fileSearch.mediaType.pdf", "PDF"],
  article: ["sidepanel:fileSearch.mediaType.article", "Article"],
  note: ["sidepanel:fileSearch.mediaType.note", "Note"],
  document: ["sidepanel:fileSearch.mediaType.document", "Document"],
  epub: ["sidepanel:fileSearch.mediaType.epub", "EPUB"],
  html: ["sidepanel:fileSearch.mediaType.html", "HTML"],
  xml: ["sidepanel:fileSearch.mediaType.xml", "XML"]
}

/**
 * Filter bar for File Search tab — media type chips + sort dropdown
 */
export const FileSearchFilters: React.FC<FileSearchFiltersProps> = ({
  mediaTypes,
  onMediaTypesChange,
  sortMode,
  onSortModeChange,
  disabled = false
}) => {
  const { t } = useTranslation(["sidepanel"])

  const selectedSet = new Set(mediaTypes)
  const isAllSelected = mediaTypes.length === 0

  const handleAllClick = () => {
    onMediaTypesChange([])
  }

  const handleTypeClick = (type: FileSearchMediaType) => {
    if (isAllSelected) {
      onMediaTypesChange([type])
    } else if (selectedSet.has(type)) {
      const next = mediaTypes.filter((t) => t !== type)
      onMediaTypesChange(next.length === 0 ? [] : next)
    } else {
      const nextSet = new Set(mediaTypes)
      nextSet.add(type)
      const next = FILE_SEARCH_MEDIA_TYPES.filter((t) => nextSet.has(t))
      onMediaTypesChange(
        next.length === FILE_SEARCH_MEDIA_TYPES.length ? [] : [...next]
      )
    }
  }

  const chipClass = (isSelected: boolean) =>
    `px-2.5 py-0.5 text-xs font-medium rounded-full transition-colors ${
      disabled ? "cursor-not-allowed" : "cursor-pointer"
    } ${
      isSelected
        ? "bg-accent text-white"
        : "bg-surface2 text-text-muted hover:bg-surface3 hover:text-text"
    } ${disabled ? "opacity-50" : ""}`

  return (
    <div className="flex items-center justify-between gap-3">
      <div
        className="flex flex-wrap gap-1.5"
        role="group"
        aria-label={t(
          "sidepanel:fileSearch.filterByType",
          "Filter by media type"
        )}
      >
        <button
          type="button"
          onClick={handleAllClick}
          disabled={disabled}
          className={chipClass(isAllSelected)}
          aria-pressed={isAllSelected}
        >
          {t("sidepanel:rag.sources.all", "All")}
        </button>
        {FILE_SEARCH_MEDIA_TYPES.map((type) => {
          const isSelected = !isAllSelected && selectedSet.has(type)
          return (
            <button
              key={type}
              type="button"
              onClick={() => handleTypeClick(type)}
              disabled={disabled}
              className={chipClass(isSelected)}
              aria-pressed={isSelected}
            >
              {t(...MEDIA_TYPE_I18N_KEYS[type])}
            </button>
          )
        })}
      </div>
      <Select
        value={sortMode}
        onChange={onSortModeChange}
        size="small"
        className="w-28 flex-shrink-0"
        disabled={disabled}
        options={[
          {
            label: t("sidepanel:rag.sort.relevance", "Relevance"),
            value: "relevance"
          },
          {
            label: t("sidepanel:rag.sort.date", "Date"),
            value: "date"
          },
          {
            label: t("sidepanel:rag.sort.type", "Type"),
            value: "type"
          }
        ]}
      />
    </div>
  )
}
