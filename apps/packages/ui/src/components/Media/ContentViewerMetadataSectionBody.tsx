import type { TFunction } from 'i18next'

import type { MediaResultItem } from './types'

interface ContentViewerMetadataSectionBodyProps {
  selectedMedia: MediaResultItem
  t: TFunction
}

export function ContentViewerMetadataSectionBody({
  selectedMedia,
  t
}: ContentViewerMetadataSectionBodyProps) {
  return (
    <div
      className="p-3 bg-surface animate-in fade-in slide-in-from-top-1 duration-150"
      data-testid="media-metadata-section-panel"
    >
      <div className="space-y-1 text-sm">
        <div className="flex justify-between py-1">
          <span className="text-text-muted text-xs">
            {t('review:mediaPage.idLabel', { defaultValue: 'ID' })}
          </span>
          <span className="text-text font-mono text-xs">
            {selectedMedia.id}
          </span>
        </div>
        {selectedMedia.meta?.type ? (
          <div className="flex justify-between py-1">
            <span className="text-text-muted text-xs">
              {t('review:mediaPage.typeLabel', { defaultValue: 'Type' })}
            </span>
            <span className="text-text text-xs capitalize">
              {selectedMedia.meta.type}
            </span>
          </div>
        ) : null}
        <div className="flex justify-between py-1">
          <span className="text-text-muted text-xs">
            {t('review:mediaPage.titleLabel', { defaultValue: 'Title' })}
          </span>
          <span className="text-text text-xs truncate max-w-[200px]">
            {selectedMedia.title ||
              t('review:mediaPage.notAvailable', { defaultValue: 'N/A' })}
          </span>
        </div>
        {selectedMedia.meta?.source ? (
          <div className="flex justify-between py-1">
            <span className="text-text-muted text-xs">
              {t('review:mediaPage.source', { defaultValue: 'Source' })}
            </span>
            <span className="text-text text-xs truncate max-w-[200px]">
              {selectedMedia.meta.source}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  )
}
