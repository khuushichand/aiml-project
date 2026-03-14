import React from "react"

import { usePresentationStudioStore } from "@/store/presentation-studio"

export const SlideEditorPane: React.FC = () => {
  const slides = usePresentationStudioStore((state) => state.slides)
  const selectedSlideId = usePresentationStudioStore((state) => state.selectedSlideId)
  const updateSlide = usePresentationStudioStore((state) => state.updateSlide)
  const slide = slides.find((entry) => entry.metadata.studio.slideId === selectedSlideId) || null

  if (!slide) {
    return (
      <section
        className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6"
        data-testid="presentation-studio-slide-editor"
      >
        <p className="text-sm text-slate-500">Select a slide to edit its content.</p>
      </section>
    )
  }

  return (
    <section
      className="flex min-h-[320px] flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4"
      data-testid="presentation-studio-slide-editor"
    >
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Slide Editor</h2>
        <p className="text-sm text-slate-500">Structured fields for the current slide.</p>
      </div>

      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
        Slide title
        <input
          className="rounded-md border border-slate-300 px-3 py-2"
          onChange={(event) =>
            updateSlide(slide.metadata.studio.slideId, { title: event.target.value })
          }
          value={slide.title || ""}
        />
      </label>

      <label className="flex flex-1 flex-col gap-2 text-sm font-medium text-slate-700">
        Slide content
        <textarea
          className="min-h-[120px] rounded-md border border-slate-300 px-3 py-2"
          onChange={(event) =>
            updateSlide(slide.metadata.studio.slideId, { content: event.target.value })
          }
          value={slide.content}
        />
      </label>

      <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
        Narration script
        <textarea
          className="min-h-[100px] rounded-md border border-slate-300 px-3 py-2"
          onChange={(event) =>
            updateSlide(slide.metadata.studio.slideId, {
              speaker_notes: event.target.value
            })
          }
          value={slide.speaker_notes || ""}
        />
      </label>
    </section>
  )
}
