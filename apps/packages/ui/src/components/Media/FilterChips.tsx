import { X, Star, Tag, FileType } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface FilterChipsProps {
  mediaTypes: string[]
  keywords: string[]
  excludedKeywords?: string[]
  showFavoritesOnly: boolean
  activeFilterCount?: number
  onRemoveMediaType: (type: string) => void
  onRemoveKeyword: (keyword: string) => void
  onRemoveExcludedKeyword?: (keyword: string) => void
  onToggleFavorites: () => void
  onClearAll: () => void
}

export function FilterChips({
  mediaTypes,
  keywords,
  excludedKeywords = [],
  showFavoritesOnly,
  activeFilterCount = 0,
  onRemoveMediaType,
  onRemoveKeyword,
  onRemoveExcludedKeyword,
  onToggleFavorites,
  onClearAll
}: FilterChipsProps) {
  const { t } = useTranslation(['review'])

  const hasFilters =
    mediaTypes.length > 0 ||
    keywords.length > 0 ||
    excludedKeywords.length > 0 ||
    showFavoritesOnly

  if (!hasFilters) return null

  const clearAllLabel =
    activeFilterCount > 0
      ? t('review:mediaPage.clearAllWithCount', {
          defaultValue: 'Clear all ({{count}})',
          count: activeFilterCount
        })
      : t('review:mediaPage.clearAll', { defaultValue: 'Clear all' })

  return (
    <div className="rounded-md border border-border bg-surface2/40 px-3 py-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className="text-xs text-text-muted font-medium"
          aria-live="polite"
          aria-atomic="true"
        >
          {t('review:mediaPage.activeFilters', { defaultValue: 'Active filters:' })}
        </span>

        {/* Favorites chip */}
        {showFavoritesOnly && (
          <button
            type="button"
            onClick={onToggleFavorites}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-warn/10 text-warn border border-warn/20 hover:bg-warn/20 transition-colors"
            title={t('review:mediaPage.removeFavoritesFilter', { defaultValue: 'Remove favorites filter' })}
          >
            <Star className="w-3 h-3 fill-warn" />
            <span>{t('review:mediaPage.favoritesOnly', { defaultValue: 'Favorites only' })}</span>
            <X className="w-3 h-3 ml-0.5" />
          </button>
        )}

        {/* Media type chips */}
        {mediaTypes.map((type) => (
          <button
            key={`type-${type}`}
            type="button"
            onClick={() => onRemoveMediaType(type)}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-primary/10 text-primaryStrong border border-primary/20 hover:bg-primary/20 transition-colors"
            title={t('review:mediaPage.removeTypeFilter', { defaultValue: 'Remove {{type}} filter', type })}
          >
            <FileType className="w-3 h-3" />
            <span className="capitalize">{type}</span>
            <X className="w-3 h-3 ml-0.5" />
          </button>
        ))}

        {/* Keyword chips */}
        {keywords.map((keyword) => (
          <button
            key={`kw-${keyword}`}
            type="button"
            onClick={() => onRemoveKeyword(keyword)}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-surface border border-border text-text hover:bg-surface2 transition-colors"
            title={t('review:mediaPage.removeKeywordFilter', { defaultValue: 'Remove "{{keyword}}" filter', keyword })}
          >
            <Tag className="w-3 h-3" />
            <span className="max-w-[100px] truncate">{keyword}</span>
            <X className="w-3 h-3 ml-0.5" />
          </button>
        ))}

        {/* Excluded keyword chips */}
        {excludedKeywords.map((keyword) => (
          <button
            key={`excluded-kw-${keyword}`}
            type="button"
            onClick={() => onRemoveExcludedKeyword?.(keyword)}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-danger/10 border border-danger/20 text-danger hover:bg-danger/20 transition-colors"
            title={t('review:mediaPage.removeExcludedKeywordFilter', {
              defaultValue: 'Remove excluded "{{keyword}}" filter',
              keyword
            })}
          >
            <Tag className="w-3 h-3" />
            <span className="max-w-[100px] truncate">-{keyword}</span>
            <X className="w-3 h-3 ml-0.5" />
          </button>
        ))}

        {/* Clear all button */}
        <button
          type="button"
          onClick={onClearAll}
          className="text-xs text-text-muted hover:text-text underline ml-1"
          title={t('review:mediaPage.clearAllFilters', { defaultValue: 'Clear all filters' })}
        >
          {clearAllLabel}
        </button>
      </div>
    </div>
  )
}
