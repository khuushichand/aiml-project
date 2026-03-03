import React from "react"
import { Button, Empty, Spin } from "antd"
import { Bookmark, Save } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { ReadingSavedSearch } from "@/types/collections"

interface SavedSearchesMenuProps {
  searches: ReadingSavedSearch[]
  loading?: boolean
  onApply: (search: ReadingSavedSearch) => void
  onCreateFromCurrent: () => void
}

export const SavedSearchesMenu: React.FC<SavedSearchesMenuProps> = ({
  searches,
  loading = false,
  onApply,
  onCreateFromCurrent
}) => {
  const { t } = useTranslation(["collections", "common"])

  return (
    <div className="rounded-lg border border-border bg-bg p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-text">
          {t("collections:reading.savedSearches", "Saved Searches")}
        </span>
        <Button
          size="small"
          icon={<Save className="h-3 w-3" />}
          onClick={onCreateFromCurrent}
        >
          {t("collections:reading.saveCurrentSearch", "Save current")}
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-3">
          <Spin size="small" />
        </div>
      ) : searches.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={t("collections:reading.savedSearchesEmpty", "No saved searches yet")}
        />
      ) : (
        <div className="flex flex-wrap gap-2">
          {searches.map((search) => (
            <Button
              key={search.id}
              size="small"
              icon={<Bookmark className="h-3 w-3" />}
              onClick={() => onApply(search)}
            >
              {search.name}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}

