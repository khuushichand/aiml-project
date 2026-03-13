import React from "react"

import { usePresentationStudioStore } from "@/store/presentation-studio"

type MediaRailProps = {
  canRender: boolean
}

export const MediaRail: React.FC<MediaRailProps> = ({ canRender }) => {
  const slides = usePresentationStudioStore((state) => state.slides)
  const selectedSlideId = usePresentationStudioStore((state) => state.selectedSlideId)
  const autosaveState = usePresentationStudioStore((state) => state.autosaveState)
  const etag = usePresentationStudioStore((state) => state.etag)
  const slide = slides.find((entry) => entry.metadata.studio.slideId === selectedSlideId) || null

  return (
    <aside
      className="flex min-h-[320px] flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4"
      data-testid="presentation-studio-media-rail"
    >
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Media & Publish</h2>
        <p className="text-sm text-slate-500">Track per-slide media state and render readiness.</p>
      </div>

      <dl className="grid grid-cols-1 gap-3 text-sm text-slate-600">
        <div>
          <dt className="font-medium text-slate-800">Audio status</dt>
          <dd>{slide?.metadata.studio.audio.status || "missing"}</dd>
        </div>
        <div>
          <dt className="font-medium text-slate-800">Image status</dt>
          <dd>{slide?.metadata.studio.image.status || "missing"}</dd>
        </div>
        <div>
          <dt className="font-medium text-slate-800">Autosave</dt>
          <dd>{autosaveState}</dd>
        </div>
        <div>
          <dt className="font-medium text-slate-800">ETag</dt>
          <dd>{etag || "unsaved"}</dd>
        </div>
        <div>
          <dt className="font-medium text-slate-800">Video render</dt>
          <dd>{canRender ? "available" : "unavailable"}</dd>
        </div>
      </dl>
    </aside>
  )
}
