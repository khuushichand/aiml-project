import React from "react"

import { usePresentationStudioStore } from "@/store/presentation-studio"

export const SlideRail: React.FC = () => {
  const slides = usePresentationStudioStore((state) => state.slides)
  const selectedSlideId = usePresentationStudioStore((state) => state.selectedSlideId)
  const selectSlide = usePresentationStudioStore((state) => state.selectSlide)
  const addSlide = usePresentationStudioStore((state) => state.addSlide)

  return (
    <aside
      className="flex min-h-[320px] flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4"
      data-testid="presentation-studio-slide-rail"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Slides</h2>
          <p className="text-sm text-slate-500">Arrange and edit your sequence.</p>
        </div>
        <button
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700"
          onClick={() => addSlide()}
          type="button"
        >
          Add slide
        </button>
      </div>

      <div className="flex flex-col gap-2">
        {slides.map((slide) => {
          const slideId = slide.metadata.studio.slideId
          const isActive = slideId === selectedSlideId
          return (
            <button
              key={slideId}
              className={`rounded-lg border px-3 py-3 text-left ${
                isActive
                  ? "border-slate-900 bg-slate-50"
                  : "border-slate-200 bg-white text-slate-700"
              }`}
              onClick={() => selectSlide(slideId)}
              type="button"
            >
              <div className="text-xs uppercase tracking-wide text-slate-400">
                {slide.layout}
              </div>
              <div className="mt-1 text-sm font-medium text-slate-900">
                {slide.title || "Untitled slide"}
              </div>
            </button>
          )
        })}
      </div>
    </aside>
  )
}
