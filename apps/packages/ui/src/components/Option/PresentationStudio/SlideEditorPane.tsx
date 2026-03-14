import React from "react"

import { Badge } from "@/components/ui/primitives/Badge"
import { PresentationStudioStatusBadge } from "./PresentationStudioStatusBadge"
import { describeSlideReadiness } from "./presentationStudioReadiness"
import { usePresentationStudioStore } from "@/store/presentation-studio"

const transitionOptions = [
  { value: "fade", label: "Fade" },
  { value: "cut", label: "Cut" },
  { value: "wipe", label: "Wipe" },
  { value: "zoom", label: "Zoom" }
] as const

export const SlideEditorPane: React.FC = () => {
  const slides = usePresentationStudioStore((state) => state.slides)
  const selectedSlideId = usePresentationStudioStore((state) => state.selectedSlideId)
  const updateSlide = usePresentationStudioStore((state) => state.updateSlide)
  const slide = slides.find((entry) => entry.metadata.studio.slideId === selectedSlideId) || null
  const slideIndex = slide
    ? slides.findIndex((entry) => entry.metadata.studio.slideId === slide.metadata.studio.slideId)
    : -1
  const readiness = slide ? describeSlideReadiness(slide) : null

  if (!slide) {
    return (
      <section
        className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6"
        data-testid="presentation-studio-slide-editor"
      >
        <p className="text-sm text-slate-500">Select a slide to edit its content.</p>
      </section>
    )
  }

  return (
    <section
      className="flex min-h-[320px] min-w-0 flex-col gap-5 overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      data-testid="presentation-studio-slide-editor"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Slide Editor</h2>
          <p className="text-sm text-slate-500">
            Shape what appears on the slide and what the narration will say.
          </p>
        </div>
        <Badge size="sm" variant="secondary">
          Slide {slideIndex + 1} of {slides.length}
        </Badge>
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0 space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-base font-semibold text-slate-900">On-slide copy</h3>
            <p className="mt-1 text-sm text-slate-500">
              This text is visible on the slide itself.
            </p>
            <div className="mt-4 space-y-4">
              <label className="flex min-w-0 flex-col gap-2 text-sm font-medium text-slate-700">
                Slide title
                <input
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  onChange={(event) =>
                    updateSlide(slide.metadata.studio.slideId, { title: event.target.value })
                  }
                  value={slide.title || ""}
                />
              </label>

              <label className="flex min-w-0 flex-1 flex-col gap-2 text-sm font-medium text-slate-700">
                Slide content
                <textarea
                  className="min-h-[140px] w-full rounded-lg border border-slate-300 px-3 py-2"
                  onChange={(event) =>
                    updateSlide(slide.metadata.studio.slideId, { content: event.target.value })
                  }
                  value={slide.content}
                />
              </label>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 className="text-base font-semibold text-slate-900">Narration</h3>
            <p className="mt-1 text-sm text-slate-500">
              This script is spoken in the generated narration audio.
            </p>
            <label className="mt-4 flex min-w-0 flex-col gap-2 text-sm font-medium text-slate-700">
              Narration script
              <textarea
                className="min-h-[140px] w-full rounded-lg border border-slate-300 px-3 py-2"
                onChange={(event) =>
                  updateSlide(slide.metadata.studio.slideId, {
                    speaker_notes: event.target.value
                  })
                }
                value={slide.speaker_notes || ""}
              />
            </label>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 className="text-base font-semibold text-slate-900">Transitions & timing</h3>
            <p className="mt-1 text-sm text-slate-500">
              Choose how this slide enters and whether timing follows narration or a manual hold.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="flex min-w-0 flex-col gap-2 text-sm font-medium text-slate-700">
                Transition
                <select
                  aria-label="Transition"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
                  onChange={(event) =>
                    updateSlide(slide.metadata.studio.slideId, {
                      metadata: {
                        studio: {
                          transition: event.target.value
                        }
                      }
                    })
                  }
                  value={slide.metadata.studio.transition}
                >
                  {transitionOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex min-w-0 flex-col gap-2 text-sm font-medium text-slate-700">
                Duration mode
                <select
                  aria-label="Duration mode"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
                  onChange={(event) =>
                    updateSlide(slide.metadata.studio.slideId, {
                      metadata: {
                        studio: {
                          timing_mode: event.target.value
                        }
                      }
                    })
                  }
                  value={slide.metadata.studio.timing_mode}
                >
                  <option value="auto">Auto from narration</option>
                  <option value="manual">Manual hold</option>
                </select>
              </label>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
              <label className="flex min-w-0 flex-col gap-2 text-sm font-medium text-slate-700">
                Manual duration (seconds)
                <input
                  aria-label="Manual duration (seconds)"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                  disabled={slide.metadata.studio.timing_mode !== "manual"}
                  min={1}
                  onChange={(event) =>
                    updateSlide(slide.metadata.studio.slideId, {
                      metadata: {
                        studio: {
                          manual_duration_ms:
                            event.target.value.trim().length > 0
                              ? Math.round(Number(event.target.value) * 1000)
                              : null
                        }
                      }
                    })
                  }
                  step={1}
                  type="number"
                  value={
                    slide.metadata.studio.manual_duration_ms
                      ? String(Math.round(slide.metadata.studio.manual_duration_ms / 1000))
                      : ""
                  }
                />
              </label>

              <Badge size="sm" variant="info">
                Effective duration: {readiness?.effectiveTiming || "Unknown"}
              </Badge>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Active transition
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-900">
                  {readiness?.transitionLabel || "Fade"}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Narration timing
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-900">
                  {readiness?.narrationTiming || "Unknown until audio is generated"}
                </p>
              </div>
            </div>
          </div>
        </div>

        <aside className="min-w-0 rounded-[28px] bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.22),_transparent_45%),linear-gradient(180deg,_#0f172a_0%,_#111827_100%)] p-4 text-white shadow-inner">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold">Preview</h3>
              <p className="text-sm text-slate-300">How this slide reads at a glance.</p>
            </div>
            <Badge className="bg-white/10 text-white" size="sm" variant="info">
              {slide.layout}
            </Badge>
          </div>

          <div className="mt-4 rounded-[24px] border border-white/10 bg-white/10 p-4">
            <div className="rounded-2xl border border-dashed border-white/20 bg-black/10 px-4 py-6 text-sm text-slate-300">
              {slide.metadata.studio.image.status === "ready"
                ? "Visual ready for this slide."
                : "Add or generate an image to support this moment."}
            </div>
            <h4 className="mt-4 text-lg font-semibold text-white">
              {slide.title || "Untitled slide"}
            </h4>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-200">
              {slide.content || "Write the key point that should remain visible while narration plays."}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <PresentationStudioStatusBadge
                className="bg-white/10 text-white"
                status={slide.metadata.studio.image.status}
              />
              <PresentationStudioStatusBadge
                className="bg-white/10 text-white"
                status={slide.metadata.studio.audio.status}
              />
              <Badge className="bg-white/10 text-white" size="sm" variant="info">
                {readiness?.transitionLabel || "Fade"}
              </Badge>
              <Badge className="bg-white/10 text-white" size="sm" variant="info">
                {readiness?.effectiveTiming || "Unknown"}
              </Badge>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-white/10 bg-black/10 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">
              Spoken summary
            </p>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-200">
              {slide.speaker_notes || "Narration will appear here once you write the spoken script."}
            </p>
          </div>
        </aside>
      </div>
    </section>
  )
}
