import React from 'react'
import { Modal } from 'antd'

type MediaExportFormat = 'json' | 'markdown' | 'text' | 'bibtex'
type ReingestSchedulePreset = 'hourly' | 'daily' | 'weekly'

type ContentViewerActionModalsProps = {
  modals: {
    exportModalOpen: boolean
    setExportModalOpen: (open: boolean) => void
    exportFormat: MediaExportFormat
    setExportFormat: (format: MediaExportFormat) => void
    confirmExportMedia: () => void
    scheduleRefreshModalOpen: boolean
    setScheduleRefreshModalOpen: (open: boolean) => void
    scheduleRefreshSubmitting: boolean
    sourceUrlForScheduling: string
    scheduleRefreshPreset: ReingestSchedulePreset
    setScheduleRefreshPreset: (preset: ReingestSchedulePreset) => void
    handleScheduleSourceRefresh: () => Promise<void>
    REINGEST_CRON_BY_PRESET: Record<ReingestSchedulePreset, string>
  }
  t: (key: string, opts?: Record<string, any>) => string
}

const EXPORT_FORMAT_OPTIONS: Array<[MediaExportFormat, string]> = [
  ['json', 'JSON'],
  ['markdown', 'Markdown'],
  ['text', 'Plain text'],
  ['bibtex', 'BibTeX']
]

const REINGEST_PRESETS: ReingestSchedulePreset[] = ['hourly', 'daily', 'weekly']

export function ContentViewerActionModals({
  modals,
  t
}: ContentViewerActionModalsProps) {
  return (
    <>
      <Modal
        open={modals.scheduleRefreshModalOpen}
        onCancel={() => {
          if (!modals.scheduleRefreshSubmitting) {
            modals.setScheduleRefreshModalOpen(false)
          }
        }}
        footer={null}
        title={t('review:mediaPage.scheduleSourceRefresh', {
          defaultValue: 'Schedule source refresh'
        })}
        destroyOnHidden
      >
        <div className="space-y-3" data-testid="media-schedule-refresh-modal">
          <p className="m-0 text-xs text-text-muted">
            {t('review:mediaPage.scheduleSourceRefreshHint', {
              defaultValue:
                'Create a watchlist monitor to re-fetch this source URL on a schedule.'
            })}
          </p>
          <p className="m-0 rounded border border-border bg-surface2 px-2 py-1 text-[11px] text-text">
            {modals.sourceUrlForScheduling ||
              t('review:mediaPage.scheduleSourceRefreshNoUrl', {
                defaultValue: 'No source URL available for scheduling.'
              })}
          </p>
          <div className="flex flex-wrap gap-2">
            {REINGEST_PRESETS.map((preset) => {
              const isActive = modals.scheduleRefreshPreset === preset
              const label =
                preset === 'hourly'
                  ? t('review:mediaPage.schedulePresetHourly', { defaultValue: 'Hourly' })
                  : preset === 'daily'
                    ? t('review:mediaPage.schedulePresetDaily', { defaultValue: 'Daily' })
                    : t('review:mediaPage.schedulePresetWeekly', { defaultValue: 'Weekly' })
              return (
                <button
                  key={preset}
                  type="button"
                  className={`rounded border px-2 py-1 text-xs transition-colors ${
                    isActive
                      ? 'border-primary bg-primary text-white'
                      : 'border-border bg-surface2 text-text hover:bg-surface'
                  }`}
                  onClick={() => modals.setScheduleRefreshPreset(preset)}
                  aria-pressed={isActive}
                  data-testid={`media-schedule-refresh-preset-${preset}`}
                >
                  {label}
                </button>
              )
            })}
          </div>
          <div className="text-xs text-text-muted" data-testid="media-schedule-refresh-cron">
            {t('review:mediaPage.scheduleSourceRefreshCron', {
              defaultValue: 'Cron: {{cron}}',
              cron: modals.REINGEST_CRON_BY_PRESET[modals.scheduleRefreshPreset]
            })}
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded border border-border px-3 py-1.5 text-xs text-text hover:bg-surface2"
              onClick={() => modals.setScheduleRefreshModalOpen(false)}
              disabled={modals.scheduleRefreshSubmitting}
            >
              {t('common:cancel', { defaultValue: 'Cancel' })}
            </button>
            <button
              type="button"
              className="rounded border border-primary bg-primary px-3 py-1.5 text-xs text-white hover:bg-primaryStrong disabled:opacity-60"
              onClick={() => {
                void modals.handleScheduleSourceRefresh()
              }}
              disabled={modals.scheduleRefreshSubmitting || !modals.sourceUrlForScheduling}
              data-testid="media-schedule-refresh-confirm"
            >
              {modals.scheduleRefreshSubmitting
                ? t('review:mediaPage.scheduleSourceRefreshSubmitting', {
                    defaultValue: 'Scheduling...'
                  })
                : t('review:mediaPage.scheduleSourceRefreshConfirm', {
                    defaultValue: 'Schedule'
                  })}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={modals.exportModalOpen}
        onCancel={() => modals.setExportModalOpen(false)}
        footer={null}
        title={t('review:mediaPage.exportMedia', {
          defaultValue: 'Export content'
        })}
        destroyOnHidden
      >
        <div className="space-y-3" data-testid="media-export-modal">
          <div className="flex flex-wrap gap-2">
            {EXPORT_FORMAT_OPTIONS.map(([format, label]) => {
              const isActive = modals.exportFormat === format
              return (
                <button
                  key={format}
                  type="button"
                  className={`rounded border px-2 py-1 text-xs transition-colors ${
                    isActive
                      ? 'border-primary bg-primary text-white'
                      : 'border-border bg-surface2 text-text hover:bg-surface'
                  }`}
                  onClick={() => modals.setExportFormat(format)}
                  aria-pressed={isActive}
                  data-testid={`media-export-format-${format}`}
                >
                  {label}
                </button>
              )
            })}
          </div>
          <div className="text-xs text-text-muted" data-testid="media-export-hint">
            {t('review:mediaPage.exportHint', {
              defaultValue: 'Exports content, analysis, and key metadata for this item.'
            })}
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded border border-border px-3 py-1.5 text-xs text-text hover:bg-surface2"
              onClick={() => modals.setExportModalOpen(false)}
            >
              {t('common:cancel', { defaultValue: 'Cancel' })}
            </button>
            <button
              type="button"
              className="rounded border border-primary bg-primary px-3 py-1.5 text-xs text-white hover:bg-primaryStrong"
              onClick={modals.confirmExportMedia}
              data-testid="media-export-confirm"
            >
              {t('review:mediaPage.exportNow', { defaultValue: 'Export' })}
            </button>
          </div>
        </div>
      </Modal>
    </>
  )
}
