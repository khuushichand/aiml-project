import React, { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import type { MediaResultItem } from '@/components/Media/types'

export type MediaLibraryStorageUsage = {
  loading: boolean
  error: string | null
  totalMb: number | null
  quotaMb: number | null
  usagePercentage: number | null
  warning: string | null
}

type MediaLibraryStatsPanelProps = {
  results: MediaResultItem[]
  totalCount: number
  storageUsage: MediaLibraryStorageUsage
}

const toPositiveFiniteNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) return value
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value)
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  return null
}

const extractWordCount = (item: MediaResultItem): number => {
  const raw = item?.raw
  const candidates = [
    raw?.word_count,
    raw?.wordCount,
    raw?.metadata?.word_count,
    raw?.metadata?.wordCount,
    raw?.safe_metadata?.word_count,
    raw?.safe_metadata?.wordCount,
    raw?.text_stats?.word_count,
    raw?.textStats?.wordCount
  ]
  for (const candidate of candidates) {
    const parsed = toPositiveFiniteNumber(candidate)
    if (parsed != null) return Math.trunc(parsed)
  }
  return 0
}

const formatInteger = (value: number): string => {
  return new Intl.NumberFormat().format(Math.max(0, Math.trunc(value)))
}

const formatMegabytes = (value: number): string => {
  return `${value.toFixed(1)} MB`
}

export const MediaLibraryStatsPanel: React.FC<MediaLibraryStatsPanelProps> = ({
  results,
  totalCount,
  storageUsage
}) => {
  const { t } = useTranslation(['review'])

  const visibleCount = Array.isArray(results) ? results.length : 0
  const normalizedTotalCount = Number.isFinite(totalCount) ? Math.max(0, totalCount) : 0

  const wordCountVisible = useMemo(() => {
    if (!Array.isArray(results) || results.length === 0) return 0
    return results.reduce((sum, item) => sum + extractWordCount(item), 0)
  }, [results])

  const typeDistribution = useMemo(() => {
    const counts = new Map<string, number>()
    for (const item of results) {
      const rawType = String(item?.meta?.type || item?.kind || '').trim().toLowerCase()
      const resolvedType = rawType.length > 0 ? rawType : 'unknown'
      counts.set(resolvedType, (counts.get(resolvedType) || 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)
  }, [results])

  return (
    <section
      className="rounded-md border border-border bg-surface2 px-2 py-2 space-y-2"
      data-testid="media-library-stats-panel"
    >
      <h3 className="text-xs font-medium text-text">
        {t('review:mediaPage.libraryStatsTitle', {
          defaultValue: 'Library stats'
        })}
      </h3>

      <div className="grid grid-cols-2 gap-2 text-[11px] text-text-muted">
        <div className="rounded border border-border bg-surface px-2 py-1">
          <p className="m-0 text-text-muted">
            {t('review:mediaPage.libraryVisibleCount', {
              defaultValue: 'Visible'
            })}
          </p>
          <p className="m-0 font-medium text-text" data-testid="media-library-stats-visible">
            {formatInteger(visibleCount)}
          </p>
        </div>
        <div className="rounded border border-border bg-surface px-2 py-1">
          <p className="m-0 text-text-muted">
            {t('review:mediaPage.libraryTotalCount', {
              defaultValue: 'Total'
            })}
          </p>
          <p className="m-0 font-medium text-text" data-testid="media-library-stats-total">
            {formatInteger(normalizedTotalCount)}
          </p>
        </div>
        <div className="rounded border border-border bg-surface px-2 py-1">
          <p className="m-0 text-text-muted">
            {t('review:mediaPage.libraryWordCount', {
              defaultValue: 'Words (visible)'
            })}
          </p>
          <p className="m-0 font-medium text-text" data-testid="media-library-stats-words">
            {formatInteger(wordCountVisible)}
          </p>
        </div>
        <div className="rounded border border-border bg-surface px-2 py-1">
          <p className="m-0 text-text-muted">
            {t('review:mediaPage.libraryTypeCount', {
              defaultValue: 'Types (visible)'
            })}
          </p>
          <p className="m-0 font-medium text-text" data-testid="media-library-stats-types">
            {formatInteger(typeDistribution.length)}
          </p>
        </div>
      </div>

      <div className="space-y-1">
        <p className="m-0 text-[11px] text-text-muted">
          {t('review:mediaPage.libraryTypeDistribution', {
            defaultValue: 'Top types'
          })}
        </p>
        {typeDistribution.length > 0 ? (
          <ul className="m-0 list-none space-y-1 p-0 text-[11px] text-text">
            {typeDistribution.map((entry) => (
              <li
                key={entry.type}
                className="flex items-center justify-between rounded border border-border bg-surface px-2 py-1"
                data-testid="media-library-stats-type-row"
              >
                <span className="truncate">{entry.type}</span>
                <span className="shrink-0 text-text-muted">{formatInteger(entry.count)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-0 text-[11px] text-text-muted">
            {t('review:mediaPage.libraryTypeDistributionEmpty', {
              defaultValue: 'No visible items yet.'
            })}
          </p>
        )}
      </div>

      <div className="rounded border border-border bg-surface px-2 py-1 text-[11px]">
        <p className="m-0 text-text-muted">
          {t('review:mediaPage.libraryStorageUsage', {
            defaultValue: 'Storage usage'
          })}
        </p>
        {storageUsage.loading ? (
          <p className="m-0 text-text-muted" data-testid="media-library-stats-storage-loading">
            {t('review:mediaPage.libraryStorageLoading', {
              defaultValue: 'Loading...'
            })}
          </p>
        ) : storageUsage.error ? (
          <p className="m-0 text-danger" data-testid="media-library-stats-storage-error">
            {storageUsage.error}
          </p>
        ) : storageUsage.totalMb != null ? (
          <div className="space-y-0.5" data-testid="media-library-stats-storage-value">
            <p className="m-0 font-medium text-text">
              {formatMegabytes(storageUsage.totalMb)}
              {storageUsage.quotaMb != null ? ` / ${formatMegabytes(storageUsage.quotaMb)}` : ''}
            </p>
            {storageUsage.usagePercentage != null ? (
              <p className="m-0 text-text-muted">
                {t('review:mediaPage.libraryStoragePercent', {
                  defaultValue: '{{percent}}% used',
                  percent: Math.max(0, Math.round(storageUsage.usagePercentage))
                })}
              </p>
            ) : null}
            {storageUsage.warning ? (
              <p className="m-0 text-warn">{storageUsage.warning}</p>
            ) : null}
          </div>
        ) : (
          <p className="m-0 text-text-muted" data-testid="media-library-stats-storage-empty">
            {t('review:mediaPage.libraryStorageUnavailable', {
              defaultValue: 'Unavailable'
            })}
          </p>
        )}
      </div>
    </section>
  )
}

export default MediaLibraryStatsPanel
