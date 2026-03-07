import React from "react"
import { Tag } from "antd"
import { X } from "lucide-react"
import { useTranslation } from "react-i18next"

export interface ActiveFilterChipsProps {
  filterTags: string[]
  folderFilterId?: string
  folderLabel?: string
  creatorFilter?: string
  createdFromDate: string
  createdToDate: string
  updatedFromDate: string
  updatedToDate: string
  hasConversationsOnly: boolean
  favoritesOnly: boolean
  onRemoveTag: (tag: string) => void
  onClearFolder: () => void
  onClearCreator: () => void
  onClearCreatedDate: () => void
  onClearUpdatedDate: () => void
  onClearConversations: () => void
  onClearFavorites: () => void
  onClearAll: () => void
}

export function ActiveFilterChips({
  filterTags,
  folderFilterId,
  folderLabel,
  creatorFilter,
  createdFromDate,
  createdToDate,
  updatedFromDate,
  updatedToDate,
  hasConversationsOnly,
  favoritesOnly,
  onRemoveTag,
  onClearFolder,
  onClearCreator,
  onClearCreatedDate,
  onClearUpdatedDate,
  onClearConversations,
  onClearFavorites,
  onClearAll
}: ActiveFilterChipsProps) {
  const { t } = useTranslation(["settings"])

  const chips: Array<{ key: string; label: string; onClose: () => void }> = []

  for (const tag of filterTags) {
    chips.push({
      key: `tag:${tag}`,
      label: `${t("settings:manageCharacters.filterChips.tag", { defaultValue: "Tag" })}: ${tag}`,
      onClose: () => onRemoveTag(tag)
    })
  }

  if (folderFilterId) {
    chips.push({
      key: "folder",
      label: `${t("settings:manageCharacters.filterChips.folder", { defaultValue: "Folder" })}: ${folderLabel || folderFilterId}`,
      onClose: onClearFolder
    })
  }

  if (creatorFilter) {
    chips.push({
      key: "creator",
      label: `${t("settings:manageCharacters.filterChips.creator", { defaultValue: "Creator" })}: ${creatorFilter}`,
      onClose: onClearCreator
    })
  }

  if (createdFromDate || createdToDate) {
    const range = [createdFromDate, createdToDate].filter(Boolean).join(" – ")
    chips.push({
      key: "created",
      label: `${t("settings:manageCharacters.filterChips.created", { defaultValue: "Created" })}: ${range}`,
      onClose: onClearCreatedDate
    })
  }

  if (updatedFromDate || updatedToDate) {
    const range = [updatedFromDate, updatedToDate].filter(Boolean).join(" – ")
    chips.push({
      key: "updated",
      label: `${t("settings:manageCharacters.filterChips.updated", { defaultValue: "Updated" })}: ${range}`,
      onClose: onClearUpdatedDate
    })
  }

  if (hasConversationsOnly) {
    chips.push({
      key: "conversations",
      label: t("settings:manageCharacters.filterChips.hasConversations", { defaultValue: "Has conversations" }),
      onClose: onClearConversations
    })
  }

  if (favoritesOnly) {
    chips.push({
      key: "favorites",
      label: t("settings:manageCharacters.filterChips.favorites", { defaultValue: "Favorites only" }),
      onClose: onClearFavorites
    })
  }

  if (chips.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="active-filter-chips">
      <span className="text-xs text-text-muted">
        {t("settings:manageCharacters.filterChips.activeFilters", {
          defaultValue: "Active filters:"
        })}
      </span>
      {chips.map((chip) => (
        <Tag
          key={chip.key}
          closable
          onClose={(e) => {
            e.preventDefault()
            chip.onClose()
          }}
          className="m-0 inline-flex items-center gap-1 text-xs"
        >
          {chip.label}
        </Tag>
      ))}
      {chips.length > 1 && (
        <button
          type="button"
          className="text-xs text-primary hover:underline"
          onClick={onClearAll}
        >
          {t("settings:manageCharacters.filterChips.clearAll", {
            defaultValue: "Clear all"
          })}
        </button>
      )}
    </div>
  )
}
