import React from "react"

import { Badge } from "@/components/ui/primitives/Badge"
import {
  deriveDeckReadiness,
  describeSlideReadiness
} from "./presentationStudioReadiness"
import { PresentationStudioStatusBadge } from "./PresentationStudioStatusBadge"
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
  const currentReadiness = slide ? describeSlideReadiness(slide) : null
  const deckReadiness = deriveDeckReadiness(slides)
  const readyToRender =
    canRender && slides.length > 0 && deckReadiness.readySlides === slides.length
  const nextSteps = [
    ...(currentReadiness?.issues || []),
    !canRender
      ? "Video rendering is disabled on this server, so export remains limited to draft editing."
      : null
  ].filter(Boolean) as string[]

  return (
    <aside
      className="flex min-h-[320px] min-w-0 flex-col gap-4 overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      data-testid="presentation-studio-media-rail"
    >
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Media & Publish</h2>
        <p className="text-sm text-slate-500">
          Keep the selected slide production-ready and watch overall deck readiness.
        </p>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-slate-900">Current slide</h3>
          <div className="flex flex-wrap items-center gap-2">
            <Badge size="sm" variant="secondary">
              {slide?.title || "Untitled slide"}
            </Badge>
            {currentReadiness ? (
              <Badge size="sm" variant={currentReadiness.isReady ? "success" : "warning"}>
                {currentReadiness.summaryLabel}
              </Badge>
            ) : null}
          </div>
        </div>
        <dl className="mt-4 space-y-3 text-sm text-slate-600">
          <div className="flex items-center justify-between gap-3">
            <dt className="font-medium text-slate-800">Audio status</dt>
            <dd>
              <PresentationStudioStatusBadge status={slide?.metadata.studio.audio.status} />
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="font-medium text-slate-800">Image status</dt>
            <dd>
              <PresentationStudioStatusBadge status={slide?.metadata.studio.image.status} />
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="font-medium text-slate-800">Video render</dt>
            <dd>
              <Badge size="sm" variant={canRender ? "success" : "secondary"}>
                {canRender ? "available" : "unavailable"}
              </Badge>
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="font-medium text-slate-800">Narration timing</dt>
            <dd className="text-right text-sm text-slate-600">
              {currentReadiness?.narrationTiming || "Unknown until audio is generated"}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="font-medium text-slate-800">Transition</dt>
            <dd className="text-right text-sm text-slate-600">
              {currentReadiness?.transitionLabel || "Fade"}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="font-medium text-slate-800">Effective duration</dt>
            <dd className="text-right text-sm text-slate-600">
              {currentReadiness?.effectiveTiming || "Unknown until audio is generated"}
            </dd>
          </div>
        </dl>
        {currentReadiness && currentReadiness.issues.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-white p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Blocking issues
            </p>
            <ul className="mt-2 space-y-2 text-sm text-slate-600">
              {currentReadiness.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <h3 className="text-base font-semibold text-slate-900">Deck readiness</h3>
        <p className="mt-1 text-sm text-slate-500">
          {readyToRender
            ? "Every slide has image and narration assets staged for rendering."
            : "Resolve missing or stale slide media before you publish a narrated video."}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Ready slides
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {deckReadiness.readySlides}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Slides needing images
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {deckReadiness.slidesMissingImages}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Slides missing narration
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {deckReadiness.slidesMissingNarration}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Slides with stale narration
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {deckReadiness.slidesWithStaleNarration}
            </p>
          </div>
        </div>
        <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Estimated narration length
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-900">
            {deckReadiness.totalNarrationDuration}
          </p>
        </div>
        <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Estimated deck runtime
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-900">
            {deckReadiness.totalDeckDuration}
          </p>
        </div>
        <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Next up
          </p>
          <ul className="mt-2 space-y-2 text-sm text-slate-600">
            {nextSteps.length > 0 ? (
              nextSteps.map((step) => <li key={step}>{step}</li>)
            ) : (
              <li>Ready to render once slide media is complete.</li>
            )}
          </ul>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <h3 className="text-base font-semibold text-slate-900">Draft sync</h3>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-800">Autosave</p>
            <p className="text-sm text-slate-500">Persist the current project draft.</p>
          </div>
          <Badge size="sm" variant={autosaveState === "error" ? "danger" : autosaveState === "saving" ? "info" : "secondary"}>
            {autosaveState}
          </Badge>
        </div>
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            ETag
          </p>
          <p className="mt-2 break-all text-sm text-slate-600">{etag || "unsaved"}</p>
        </div>
      </section>
    </aside>
  )
}
