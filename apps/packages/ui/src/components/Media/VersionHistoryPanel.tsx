import { useState, useEffect, useCallback, useRef } from 'react'
import {
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  History,
  Copy,
  FileText,
  RotateCcw,
  Trash2,
  MoreHorizontal,
  Loader2
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Dropdown, message, Checkbox } from 'antd'
import type { MenuProps } from 'antd'
import { bgRequest } from '@/services/background-proxy'
import { useConfirmDanger } from '@/components/Common/confirm-danger'

interface VersionHistoryPanelProps {
  mediaId: string | number
  onVersionLoad?: (content: string, analysis: string, prompt: string, versionNumber: number) => void
  onRefresh?: () => void
  onShowDiff?: (
    leftText: string,
    rightText: string,
    leftLabel: string,
    rightLabel: string,
    metadataDiff?: VersionMetadataDiffSummary
  ) => void
  currentVersionNumber?: number
  defaultExpanded?: boolean
  currentContent?: string
  currentPrompt?: string
  currentAnalysis?: string
}

interface Version {
  version_number?: number
  version?: number
  analysis_content?: string
  analysis?: string
  prompt?: string
  content?: string
  created_at?: string
  updated_at?: string
  timestamp?: string
  safe_metadata?: Record<string, unknown> | string | null
}

interface VersionMetadataEntry {
  key: string
  label: string
  value: string
}

export interface VersionMetadataDiffSummary {
  left: string[]
  right: string[]
  changed: string[]
}

const VERSION_METADATA_FIELDS: Array<{ key: string; label: string; paths: string[] }> = [
  { key: 'doi', label: 'DOI', paths: ['doi', 'DOI', 'identifiers.doi', 'citation.doi'] },
  { key: 'pmid', label: 'PMID', paths: ['pmid', 'PMID', 'identifiers.pmid', 'citation.pmid'] },
  { key: 'journal', label: 'Journal', paths: ['journal', 'publication', 'citation.journal'] },
  { key: 'license', label: 'License', paths: ['license', 'rights.license', 'source.license'] }
]

export function VersionHistoryPanel({
  mediaId,
  onVersionLoad,
  onRefresh,
  onShowDiff,
  currentVersionNumber,
  defaultExpanded = false,
  currentContent = '',
  currentPrompt = '',
  currentAnalysis = ''
}: VersionHistoryPanelProps) {
  const { t } = useTranslation(['review'])
  const confirmDanger = useConfirmDanger()

  const [expanded, setExpanded] = useState(defaultExpanded)
  const [versions, setVersions] = useState<Version[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const [onlyWithAnalysis, setOnlyWithAnalysis] = useState(false)
  const [page, setPage] = useState(1)
  const [savingNewVersion, setSavingNewVersion] = useState(false)
  const selectedIndexRef = useRef(selectedIndex)
  const pageSize = 10

  // Helper functions
  const getVersionNumber = (v: Version): number | undefined =>
    typeof v?.version_number === 'number' ? v.version_number :
    (typeof v?.version === 'number' ? v.version : undefined)

  const getVersionAnalysis = (v: Version): string =>
    String(v?.analysis_content || v?.analysis || '')

  const getVersionPrompt = (v: Version): string =>
    String(v?.prompt || '')

  const getVersionTimestamp = (v: Version): string =>
    String(v?.created_at || v?.updated_at || v?.timestamp || '')

  const formatTimestamp = (ts: string): string => {
    if (!ts) return ''
    try {
      const d = new Date(ts)
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return ts
    }
  }

  const parseSafeMetadata = (v: Version): Record<string, unknown> | null => {
    const raw = v?.safe_metadata
    if (!raw) return null
    if (typeof raw === 'string') {
      try {
        const parsed = JSON.parse(raw)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          return parsed as Record<string, unknown>
        }
      } catch {
        return null
      }
      return null
    }
    if (typeof raw === 'object' && !Array.isArray(raw)) {
      return raw as Record<string, unknown>
    }
    return null
  }

  const getMetadataPathValue = (metadata: Record<string, unknown>, path: string): unknown => {
    const parts = path.split('.')
    let cursor: unknown = metadata
    for (const part of parts) {
      if (!cursor || typeof cursor !== 'object' || Array.isArray(cursor)) return undefined
      cursor = (cursor as Record<string, unknown>)[part]
    }
    return cursor
  }

  const getMetadataFieldValue = (
    metadata: Record<string, unknown>,
    paths: string[]
  ): string | null => {
    for (const path of paths) {
      const raw = getMetadataPathValue(metadata, path)
      if (raw == null) continue
      if (typeof raw === 'string' && raw.trim().length > 0) return raw.trim()
      if (typeof raw === 'number' || typeof raw === 'boolean') return String(raw)
    }
    return null
  }

  const getVersionMetadataEntries = (v: Version): VersionMetadataEntry[] => {
    const metadata = parseSafeMetadata(v)
    if (!metadata) return []
    const entries: VersionMetadataEntry[] = []

    for (const field of VERSION_METADATA_FIELDS) {
      const value = getMetadataFieldValue(metadata, field.paths)
      if (!value) continue
      entries.push({ key: field.key, label: field.label, value })
    }

    return entries
  }

  const buildMetadataDiffSummary = (
    leftEntries: VersionMetadataEntry[],
    rightEntries: VersionMetadataEntry[]
  ): VersionMetadataDiffSummary => {
    const leftByKey = new Map(leftEntries.map((entry) => [entry.key, entry]))
    const rightByKey = new Map(rightEntries.map((entry) => [entry.key, entry]))
    const allKeys = new Set<string>([...leftByKey.keys(), ...rightByKey.keys()])
    const changed: string[] = []

    for (const key of allKeys) {
      const left = leftByKey.get(key)
      const right = rightByKey.get(key)
      const leftValue = left?.value || '—'
      const rightValue = right?.value || '—'
      if (leftValue !== rightValue) {
        changed.push(`${left?.label || right?.label || key}: ${leftValue} → ${rightValue}`)
      }
    }

    return {
      left: leftEntries.map((entry) => `${entry.label}: ${entry.value}`),
      right: rightEntries.map((entry) => `${entry.label}: ${entry.value}`),
      changed
    }
  }

  useEffect(() => {
    selectedIndexRef.current = selectedIndex
  }, [selectedIndex])

  // Load versions
  const loadVersions = useCallback(async () => {
    if (!mediaId) return
    setLoading(true)
    try {
      const data = await bgRequest<any>({
        path: `/api/v1/media/${mediaId}/versions?include_content=false&limit=50&page=1` as any,
        method: 'GET' as any
      })
      const arr = Array.isArray(data) ? data : (data?.items || [])
      setVersions(arr)
      if (arr.length > 0 && selectedIndexRef.current < 0) {
        setSelectedIndex(0)
      }
    } catch (err) {
      console.error('Failed to load versions:', err)
      setVersions([])
    } finally {
      setLoading(false)
    }
  }, [mediaId])

  useEffect(() => {
    if (expanded && mediaId) {
      loadVersions()
    }
  }, [expanded, mediaId, loadVersions])

  // Filter versions - M5: Track count for badge
  const filteredVersions = onlyWithAnalysis
    ? versions.filter(v => getVersionAnalysis(v).trim().length > 0)
    : versions

  const versionsWithAnalysisCount = versions.filter(v => getVersionAnalysis(v).trim().length > 0).length

  // Paginate
  const totalPages = Math.ceil(filteredVersions.length / pageSize)
  const paginatedVersions = filteredVersions.slice((page - 1) * pageSize, page * pageSize)

  // Load version with content
  const handleLoadVersion = async (v: Version) => {
    const vNum = getVersionNumber(v)
    if (vNum === undefined) return

    try {
      const data = await bgRequest<any>({
        path: `/api/v1/media/${mediaId}/versions/${vNum}?include_content=true` as any,
        method: 'GET' as any
      })
      const content = String(data?.content || data?.raw_content || '')
      const analysis = String(data?.analysis_content || data?.analysis || '')
      const prompt = String(data?.prompt || '')

      if (onVersionLoad) {
        onVersionLoad(content, analysis, prompt, vNum)
      }
      message.success(t('mediaPage.versionLoaded', 'Version loaded'))
    } catch (err) {
      console.error('Failed to load version:', err)
      message.error(t('mediaPage.loadFailed', 'Failed to load version'))
    }
  }

  // Rollback to version
  const handleRollback = async (v: Version) => {
    const vNum = getVersionNumber(v)
    if (vNum === undefined) return

    const ok = await confirmDanger({
      title: t('mediaPage.confirmRollback', 'Rollback to this version?'),
      content: t('mediaPage.rollbackWarning', 'This will restore version {{num}} as the current version.', { num: vNum }),
      okText: t('mediaPage.rollback', 'Rollback'),
      cancelText: t('common:cancel', 'Cancel')
    })
    if (!ok) return

    try {
      await bgRequest<any>({
        path: `/api/v1/media/${mediaId}/versions/rollback` as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: { version_number: vNum }
      })
      message.info(
        t('mediaPage.rollbackKeywordsNotice', 'Rolled back to version {{num}}. Keywords were not changed.', { num: vNum }),
        5
      )
      loadVersions()
      if (onRefresh) onRefresh()
    } catch (err) {
      console.error('Rollback failed:', err)
      message.error(t('mediaPage.rollbackFailed', 'Failed to rollback'))
    }
  }

  // Delete version
  const handleDeleteVersion = async (v: Version) => {
    const vNum = getVersionNumber(v)
    if (vNum === undefined) return

    const ok = await confirmDanger({
      title: t('mediaPage.confirmDelete', 'Delete this version?'),
      content: t('mediaPage.deleteWarning', 'This will permanently delete version {{num}}.', { num: vNum }),
      okText: t('common:delete', 'Delete'),
      cancelText: t('common:cancel', 'Cancel')
    })
    if (!ok) return

    try {
      await bgRequest<any>({
        path: `/api/v1/media/${mediaId}/versions/${vNum}` as any,
        method: 'DELETE' as any
      })
      message.success(t('mediaPage.versionDeleted', 'Version deleted'))
      loadVersions()
    } catch (err) {
      console.error('Delete failed:', err)
      message.error(t('mediaPage.deleteFailed', 'Failed to delete version'))
    }
  }

  // Copy all analyses
  const handleCopyAll = () => {
    // Check for Clipboard API availability
    if (!navigator.clipboard?.writeText) {
      message.error(t('mediaPage.copyNotSupported', 'Copy is not supported in this context'))
      return
    }

    const texts = filteredVersions
      .map(v => {
        const num = getVersionNumber(v)
        const analysis = getVersionAnalysis(v)
        return analysis ? `[Version ${num}]\n${analysis}` : null
      })
      .filter(Boolean)
      .join('\n\n---\n\n')

    if (texts) {
      navigator.clipboard.writeText(texts)
        .then(() => message.success(t('mediaPage.allCopied', 'All analyses copied')))
        .catch(() => message.error(t('mediaPage.copyFailed', 'Copy failed')))
    } else {
      message.info(t('mediaPage.nothingToCopy', 'No analyses to copy'))
    }
  }

  // Copy as markdown
  const handleCopyMd = () => {
    // Check for Clipboard API availability
    if (!navigator.clipboard?.writeText) {
      message.error(t('mediaPage.copyNotSupported', 'Copy is not supported in this context'))
      return
    }

    const md = filteredVersions
      .map(v => {
        const num = getVersionNumber(v)
        const analysis = getVersionAnalysis(v)
        const ts = formatTimestamp(getVersionTimestamp(v))
        return analysis ? `## Version ${num}${ts ? ` (${ts})` : ''}\n\n${analysis}` : null
      })
      .filter(Boolean)
      .join('\n\n---\n\n')

    if (md) {
      navigator.clipboard.writeText(md)
        .then(() => message.success(t('mediaPage.markdownCopied', 'Copied as markdown')))
        .catch(() => message.error(t('mediaPage.copyFailed', 'Copy failed')))
    } else {
      message.info(t('mediaPage.nothingToCopy', 'No analyses to copy'))
    }
  }

  const resolveSnapshotForNewVersion = useCallback(async () => {
    let content = String(currentContent || '')
    let prompt = String(currentPrompt || '')
    let analysis = String(currentAnalysis || '')

    if (content.trim() && prompt.trim() && analysis.trim()) {
      return { content, prompt, analysis }
    }

    try {
      const listData = await bgRequest<any>({
        path: `/api/v1/media/${mediaId}/versions?include_content=false&limit=50&page=1` as any,
        method: 'GET' as any
      })
      const arr = Array.isArray(listData) ? listData : (listData?.items || [])

      if (arr.length > 0) {
        const latest = arr.reduce((best: Version | null, candidate: Version) => {
          if (!best) return candidate
          const bestNum = getVersionNumber(best) ?? -Infinity
          const candidateNum = getVersionNumber(candidate) ?? -Infinity
          return candidateNum > bestNum ? candidate : best
        }, null)

        if (latest) {
          if (!prompt.trim()) {
            prompt = getVersionPrompt(latest)
          }
          if (!analysis.trim()) {
            analysis = getVersionAnalysis(latest)
          }

          if (!content.trim()) {
            const latestNum = getVersionNumber(latest)
            if (latestNum !== undefined) {
              const detail = await bgRequest<any>({
                path: `/api/v1/media/${mediaId}/versions/${latestNum}?include_content=true` as any,
                method: 'GET' as any
              })
              content = String(detail?.content || detail?.raw_content || '')
              if (!prompt.trim()) {
                prompt = String(detail?.prompt || '')
              }
              if (!analysis.trim()) {
                analysis = String(detail?.analysis_content || detail?.analysis || '')
              }
            }
          }
        }
      }
    } catch (err) {
      console.error('Failed to resolve snapshot for manual version save:', err)
    }

    return { content, prompt, analysis }
  }, [currentAnalysis, currentContent, currentPrompt, mediaId])

  const handleSaveAsVersion = useCallback(async () => {
    if (!mediaId || savingNewVersion) return

    setSavingNewVersion(true)
    try {
      const snapshot = await resolveSnapshotForNewVersion()
      const content = String(snapshot?.content || '')
      const prompt = String(snapshot?.prompt || '')
      const analysis = String(snapshot?.analysis || '')

      if (!content.trim()) {
        message.warning(t('mediaPage.noContent', 'No content available'))
        return
      }

      await bgRequest<any>({
        path: `/api/v1/media/${mediaId}/versions` as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: {
          content,
          prompt,
          analysis_content: analysis
        }
      })
      message.success(t('mediaPage.versionSaved', 'Saved as new version'))
      await loadVersions()
      if (onRefresh) onRefresh()
    } catch (err) {
      console.error('Failed to save version:', err)
      message.error(t('mediaPage.saveFailed', 'Failed to save version'))
    } finally {
      setSavingNewVersion(false)
    }
  }, [loadVersions, mediaId, onRefresh, resolveSnapshotForNewVersion, savingNewVersion, t])

  // Show diff between selected and another version
  const handleShowDiff = (v: Version) => {
    if (!onShowDiff || selectedIndex < 0) return
    const selectedV = filteredVersions[selectedIndex]
    if (!selectedV) return

    const leftNum = getVersionNumber(selectedV)
    const rightNum = getVersionNumber(v)
    const leftText = getVersionAnalysis(selectedV)
    const rightText = getVersionAnalysis(v)
    const leftMetadataEntries = getVersionMetadataEntries(selectedV)
    const rightMetadataEntries = getVersionMetadataEntries(v)
    const metadataDiff = buildMetadataDiffSummary(leftMetadataEntries, rightMetadataEntries)
    const hasMetadataDiff =
      metadataDiff.left.length > 0 ||
      metadataDiff.right.length > 0 ||
      metadataDiff.changed.length > 0

    if (hasMetadataDiff) {
      onShowDiff(
        leftText,
        rightText,
        `Version ${leftNum}`,
        `Version ${rightNum}`,
        metadataDiff
      )
      return
    }

    onShowDiff(leftText, rightText, `Version ${leftNum}`, `Version ${rightNum}`)
  }

  const getVersionMenuItems = (v: Version, idx: number): MenuProps['items'] => [
    {
      key: 'load',
      label: t('mediaPage.loadVersion', 'Load into editor'),
      icon: <FileText className="w-4 h-4" />,
      onClick: () => handleLoadVersion(v)
    },
    ...(onShowDiff && selectedIndex >= 0 && selectedIndex !== idx ? [{
      key: 'diff',
      label: t('mediaPage.showDiff', 'Compare with selected'),
      onClick: () => handleShowDiff(v)
    }] : []),
    { type: 'divider' as const },
    {
      key: 'rollback',
      label: t('mediaPage.rollbackVersion', 'Rollback to this version'),
      icon: <RotateCcw className="w-4 h-4" />,
      onClick: () => handleRollback(v)
    },
    {
      key: 'delete',
      label: t('mediaPage.deleteVersion', 'Delete version'),
      icon: <Trash2 className="w-4 h-4" />,
      danger: true,
      onClick: () => handleDeleteVersion(v)
    }
  ]

  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-surface2 hover:bg-surface transition-colors text-text"
        title={t('mediaPage.versionHistory', 'Version History')}
      >
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-text-subtle" />
          <span className="text-sm font-medium text-text">
            {t('mediaPage.versionHistory', 'Version History')}
          </span>
          {versions.length > 0 && (
            <span className="text-xs text-text-muted">
              ({versions.length})
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-text-subtle" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-subtle" />
        )}
      </button>

      {expanded && (
        <div className="p-3 bg-surface animate-in fade-in slide-in-from-top-1 duration-150">
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin text-text-subtle" />
            </div>
          ) : versions.length === 0 ? (
            <div className="text-sm text-text-muted text-center py-4">
              {t('mediaPage.noVersions', 'No versions available')}
            </div>
          ) : (
            <>
              {/* Toolbar */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={onlyWithAnalysis}
                    onChange={e => {
                      setOnlyWithAnalysis(e.target.checked)
                      setPage(1)
                      // Reset selection when filter changes to avoid out-of-sync state
                      setSelectedIndex(-1)
                    }}
                  >
                    <span className="text-xs text-text-muted">
                      {t('mediaPage.onlyWithAnalysis', 'Only with analysis')}
                    </span>
                  </Checkbox>
                  {/* M5: Show count badge when filter is active */}
                  {onlyWithAnalysis && versionsWithAnalysisCount > 0 && (
                    <span className="px-1.5 py-0.5 text-[10px] bg-primary/10 text-primaryStrong rounded font-medium">
                      {versionsWithAnalysisCount} {t('mediaPage.withAnalysis', 'with analysis')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={handleSaveAsVersion}
                    disabled={savingNewVersion}
                    className="px-2 py-1 text-xs bg-primary/10 text-primaryStrong hover:bg-primary/20 rounded transition-colors inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                    title={t('mediaPage.saveAsVersion', 'Save as New Version')}
                  >
                    {savingNewVersion ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : null}
                    {savingNewVersion
                      ? t('mediaPage.savingVersion', 'Saving...')
                      : t('mediaPage.saveVersionShort', 'Save Version')}
                  </button>
                  <button
                    onClick={handleCopyAll}
                    className="px-2 py-1 text-xs text-text-muted hover:bg-surface2 rounded transition-colors"
                    title={t('mediaPage.copyAll', 'Copy All')}
                  >
                    {t('mediaPage.copyAllShort', 'Copy All')}
                  </button>
                  <button
                    onClick={handleCopyMd}
                    className="px-2 py-1 text-xs text-text-muted hover:bg-surface2 rounded transition-colors"
                    title={t('mediaPage.copyMd', 'Copy as Markdown')}
                  >
                    {t('mediaPage.copyMdShort', 'Copy MD')}
                  </button>
                </div>
              </div>

              {/* Version List */}
              <div className="space-y-2">
                {paginatedVersions.map((v, idx) => {
                  const globalIdx = (page - 1) * pageSize + idx
                  const vNum = getVersionNumber(v)
                  const analysis = getVersionAnalysis(v)
                  const timestamp = formatTimestamp(getVersionTimestamp(v))
                  const metadataEntries = getVersionMetadataEntries(v)
                  const isCurrent = vNum === currentVersionNumber
                  const isSelected = globalIdx === selectedIndex

                  return (
                    <div
                      key={vNum || idx}
                      onClick={() => setSelectedIndex(globalIdx)}
                      className={`p-2 rounded border transition-colors cursor-pointer ${
                        isSelected
                          ? 'border-primary bg-surface2'
                          : 'border-border hover:bg-surface2'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-text">
                            v{vNum}
                          </span>
                          {isCurrent && (
                            <span className="px-1.5 py-0.5 text-[10px] bg-success/10 text-success rounded">
                              {t('mediaPage.currentVersion', 'Current')}
                            </span>
                          )}
                          {analysis && (
                            <span className="px-1.5 py-0.5 text-[10px] bg-primary/10 text-primaryStrong rounded">
                              {t('mediaPage.hasAnalysis', 'Has analysis')}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          {timestamp && (
                            <span className="text-[10px] text-text-subtle">
                              {timestamp}
                            </span>
                          )}
                          <Dropdown
                            menu={{ items: getVersionMenuItems(v, globalIdx) }}
                            trigger={['click']}
                            placement="bottomRight"
                          >
                            <button
                              onClick={e => e.stopPropagation()}
                              className="p-1 text-text-subtle hover:text-text"
                              title={t('mediaPage.actionsLabel', 'Actions')}
                            >
                              <MoreHorizontal className="w-3.5 h-3.5" />
                            </button>
                          </Dropdown>
                        </div>
                      </div>
                      {analysis && (
                        <div className="mt-1 text-xs text-text-muted line-clamp-2">
                          {analysis.substring(0, 150)}
                          {analysis.length > 150 && '...'}
                        </div>
                      )}
                      {metadataEntries.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {metadataEntries.map((entry) => (
                            <span
                              key={entry.key}
                              className="px-1.5 py-0.5 text-[10px] bg-surface2 border border-border rounded text-text-muted"
                              title={`${entry.label}: ${entry.value}`}
                            >
                              {entry.label}: {entry.value}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-border">
                  <span className="text-xs text-text-muted">
                    {t('mediaPage.pageOf', 'Page {{current}} of {{total}}', { current: page, total: totalPages })}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="p-1 text-text-muted hover:bg-surface2 rounded disabled:opacity-40 disabled:cursor-not-allowed"
                      title={t('mediaPage.previousPage', 'Previous page')}
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                      className="p-1 text-text-muted hover:bg-surface2 rounded disabled:opacity-40 disabled:cursor-not-allowed"
                      title={t('mediaPage.nextPage', 'Next page')}
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
