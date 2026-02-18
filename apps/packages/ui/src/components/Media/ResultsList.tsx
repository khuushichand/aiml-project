import { FileText, Loader2, Star } from 'lucide-react'
import { Tooltip, Button } from 'antd'
import { useTranslation } from 'react-i18next'
import { formatRelativeTime } from '@/utils/dateFormatters'
import { highlightMatches } from '@/components/Media/highlightMatches'

interface Result {
  id: string | number
  title?: string
  kind: 'media' | 'note'
  snippet?: string
  keywords?: string[]
  meta?: {
    type?: string
    source?: string | null
    duration?: number | null
    status?: any
    created_at?: string
  }
}

interface ResultsListProps {
  results: Result[]
  selectedId: string | number | null
  onSelect: (id: string | number) => void
  totalCount: number
  loadedCount: number
  isLoading?: boolean
  hasActiveFilters?: boolean
  searchQuery?: string
  onClearSearch?: () => void
  onClearFilters?: () => void
  onOpenQuickIngest?: () => void
  favorites?: Set<string>
  onToggleFavorite?: (id: string) => void
  selectionMode?: boolean
  selectedIds?: Set<string>
  onToggleSelected?: (id: string | number) => void
}

export function ResultsList({
  results,
  selectedId,
  onSelect,
  totalCount,
  loadedCount,
  isLoading = false,
  hasActiveFilters = false,
  searchQuery = '',
  onClearSearch,
  onClearFilters,
  onOpenQuickIngest,
  favorites,
  onToggleFavorite,
  selectionMode = false,
  selectedIds,
  onToggleSelected
}: ResultsListProps) {
  const { t } = useTranslation(['review'])
  const hasSearchQuery = searchQuery.trim().length > 0

  const buildInspectorTooltip = (result: Result) => {
    const title = result.title || `${result.kind} ${result.id}`
    const lines: Array<{
      label: string
      value: string
      multiline?: boolean
      preserveWhitespace?: boolean
    }> = [
      {
        label: t('mediaPage.titleLabel', 'Title'),
        value: title
      },
      {
        label: t('mediaPage.typeLabel', 'Type'),
        value: result.meta?.type || result.kind
      }
    ]
    if (result.meta?.source) {
      lines.push({
        label: t('mediaPage.source', 'Source'),
        value: result.meta.source
      })
    }
    if (result.meta?.created_at) {
      lines.push({
        label: t('mediaPage.ingested', 'Ingested'),
        value: formatRelativeTime(result.meta.created_at, t, { compact: true })
      })
    }
    if (result.snippet) {
      lines.push({
        label: t('mediaPage.previewLabel', 'Preview'),
        value: result.snippet,
        multiline: true,
        preserveWhitespace: true
      })
    }
    if (Array.isArray(result.keywords) && result.keywords.length > 0) {
      lines.push({
        label: t('mediaPage.keywords', 'Keywords'),
        value: result.keywords.join(', '),
        multiline: true
      })
    }

    return (
      <div className="space-y-1 text-xs max-w-xs">
        {lines.map((line, index) => (
          <div
            key={`${line.label}-${index}`}
            className={line.multiline ? "flex flex-col gap-1" : "flex gap-1"}
          >
            <span className="font-medium text-text">{line.label}:</span>
            <span
              className={
                line.multiline
                  ? `text-text-subtle break-words line-clamp-4 ${
                      line.preserveWhitespace ? "whitespace-pre-wrap" : "whitespace-normal"
                    }`
                  : "text-text-subtle break-words"
              }
            >
              {line.value}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div>
      {/* Results Header */}
      <div className="px-4 py-2 bg-surface2 border-b border-border flex items-center justify-between sticky top-0">
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted font-medium uppercase">
            {t('mediaPage.results', 'Results')}
          </span>
          <span className="text-xs text-text">
            {loadedCount} / {totalCount}
          </span>
        </div>
      </div>

      {/* Results List */}
      <div className="divide-y divide-border">
        {/* Skeleton loading */}
        {isLoading && results.length === 0 ? (
          <>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="px-4 py-2.5 animate-pulse">
                <div className="flex items-start gap-2.5">
                  <div className="w-4 h-4 bg-surface2 rounded mt-0.5" />
                  <div className="flex-1">
                    <div className="flex gap-1.5 mb-1">
                      <div className="w-12 h-4 bg-surface2 rounded" />
                      <div className="w-16 h-4 bg-surface2 rounded" />
                    </div>
                    <div className="w-3/4 h-4 bg-surface2 rounded mb-1" />
                    <div className="w-1/2 h-3 bg-surface2 rounded" />
                  </div>
                </div>
              </div>
            ))}
          </>
        ) : results.length === 0 && !isLoading ? (
          <div className="px-4 py-6 text-center">
            {hasActiveFilters ? (
              <>
                <p className="text-text-muted text-sm mb-2">
                  {t('mediaPage.noMatchingResults', 'No results match your filters')}
                </p>
                <p className="text-xs text-text-subtle mb-3">
                  {t('mediaPage.noMatchingResultsHint', 'Try broadening your query or removing filters.')}
                </p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {hasSearchQuery && onClearSearch && (
                    <Button size="small" onClick={onClearSearch}>
                      {t('mediaPage.clearSearch', 'Clear search')}
                    </Button>
                  )}
                  {onClearFilters && (
                    <Button size="small" onClick={onClearFilters}>
                      {t('mediaPage.clearFilters', 'Clear filters')}
                    </Button>
                  )}
                  {onOpenQuickIngest && (
                    <Button size="small" onClick={onOpenQuickIngest}>
                      {t('mediaPage.openQuickIngest', 'Open Quick Ingest')}
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <>
                <p className="text-text-muted text-sm mb-2">
                  {t('mediaPage.noResults', 'No results found')}
                </p>
                <p className="text-xs text-text-subtle mb-3">
                  {t('mediaPage.noResultsHint', 'Try broader terms, or ingest new content to search.')}
                </p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {hasSearchQuery && onClearSearch && (
                    <Button size="small" onClick={onClearSearch}>
                      {t('mediaPage.clearSearch', 'Clear search')}
                    </Button>
                  )}
                  {onOpenQuickIngest && (
                    <Button size="small" onClick={onOpenQuickIngest}>
                      {t('mediaPage.openQuickIngest', 'Open Quick Ingest')}
                    </Button>
                  )}
                </div>
              </>
            )}
          </div>
        ) : (
          results.map((result) => {
            const relativeDate = result.meta?.created_at
              ? formatRelativeTime(result.meta.created_at, t, { compact: true })
              : null
            const bulkSelected = selectedIds?.has(String(result.id)) === true
            const showSelectedStyle = selectionMode ? bulkSelected : selectedId === result.id

            return (
              <div
              role="button"
              tabIndex={0}
              key={result.id}
              onClick={() => {
                if (selectionMode && onToggleSelected) {
                  onToggleSelected(result.id)
                  return
                }
                onSelect(result.id)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  if (selectionMode && onToggleSelected) {
                    onToggleSelected(result.id)
                    return
                  }
                  onSelect(result.id)
                }
              }}
              aria-label={t('mediaPage.selectResult', 'Select {{type}}: {{title}}', {
                type: result.kind,
                title: result.title || `${result.kind} ${result.id}`
              })}
              aria-selected={showSelectedStyle}
              className={`w-full py-2.5 text-left hover:bg-surface2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-inset cursor-pointer ${
                showSelectedStyle
                  ? 'bg-surface2 border-l-4 border-l-primary px-3'
                  : 'px-4'
              }`}
            >
              <div className="flex items-start gap-2.5">
                {selectionMode && (
                  <input
                    type="checkbox"
                    checked={bulkSelected}
                    onChange={() => onToggleSelected?.(result.id)}
                    onClick={(event) => event.stopPropagation()}
                    className="mt-1 h-4 w-4 rounded border-border bg-surface"
                    aria-label={t('mediaPage.selectResultCheckbox', {
                      defaultValue: 'Select {{title}}',
                      title: result.title || `${result.kind} ${result.id}`
                    })}
                    data-testid={`results-select-${String(result.id)}`}
                  />
                )}
                <div className="mt-0.5 flex flex-col items-center gap-1">
                  <FileText className="w-4 h-4 text-text-subtle" />
                  {onToggleFavorite && (
                    <Tooltip title={favorites?.has(String(result.id)) ? t('mediaPage.unfavorite', 'Remove from favorites') : t('mediaPage.favorite', 'Add to favorites')}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onToggleFavorite(String(result.id))
                        }}
                        className="p-1.5 hover:bg-surface2 rounded transition-colors"
                        aria-label={favorites?.has(String(result.id)) ? t('mediaPage.unfavorite', 'Remove from favorites') : t('mediaPage.favorite', 'Add to favorites')}
                        title={favorites?.has(String(result.id)) ? t('mediaPage.unfavorite', 'Remove from favorites') : t('mediaPage.favorite', 'Add to favorites')}
                      >
                        <Star className={`w-3.5 h-3.5 ${
                          favorites?.has(String(result.id))
                            ? 'text-warn fill-warn'
                            : 'text-text-subtle'
                        }`} />
                      </button>
                    </Tooltip>
                  )}
                </div>
                <Tooltip placement="right" title={buildInspectorTooltip(result)}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-primary/10 text-primaryStrong">
                        {result.kind.toUpperCase()}
                      </span>
                      {result.meta?.type && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-surface2 text-text capitalize">
                          {result.meta.type}
                        </span>
                      )}
                      {relativeDate && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-surface2 text-text-muted">
                          {relativeDate}
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-text truncate font-medium">
                      {result.title || `${result.kind} ${result.id}`}
                    </div>
                    {result.snippet && (
                      <div className="text-xs text-text-muted mt-0.5 line-clamp-1">
                        {highlightMatches(result.snippet, searchQuery)}
                      </div>
                    )}
                    {Array.isArray(result.keywords) && result.keywords.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {result.keywords.slice(0, 5).map((keyword, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-surface2 text-text line-clamp-1 max-w-[120px]"
                            title={keyword}
                          >
                            {keyword}
                          </span>
                        ))}
                        {result.keywords.length > 5 && (
                          <Tooltip
                            title={t('mediaPage.moreTags', '+{{count}} more tags', { count: result.keywords.length - 5 })}
                          >
                            <span className="inline-flex items-center px-2 py-0.5 text-xs text-text-muted">
                              +{result.keywords.length - 5}
                            </span>
                          </Tooltip>
                        )}
                      </div>
                    )}
                    {result.meta?.source && (
                      <div className="text-xs text-text-subtle mt-0.5">
                        {result.meta.source}
                      </div>
                    )}
                  </div>
                </Tooltip>
              </div>
            </div>
            )
          })
        )}
        {/* Loading indicator */}
        {isLoading && (
          <div className="px-4 py-3 text-center text-text-muted flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">{t('mediaPage.loadingMore', 'Loading more results...')}</span>
          </div>
        )}
      </div>
    </div>
  )
}
