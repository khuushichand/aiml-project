import React, { useCallback } from "react"
import { GripVertical } from "lucide-react"
import { DragDropProvider, type DragDropEvents } from "@dnd-kit/react"
import { useSortable } from "@dnd-kit/react/sortable"
import { closestCenter } from "@dnd-kit/collision"

import { Badge } from "@/components/ui/primitives/Badge"
import {
  deriveDeckReadiness,
  describeSlideReadiness
} from "./presentationStudioReadiness"
import { PresentationStudioStatusBadge } from "./PresentationStudioStatusBadge"
import { usePresentationStudioStore, type PresentationStudioEditorSlide } from "@/store/presentation-studio"

type DragEndEvent = Parameters<DragDropEvents["dragend"]>[0]

type SortableSlideCardProps = {
  slide: PresentationStudioEditorSlide
  index: number
  isActive: boolean
  onSelect: (slideId: string) => void
}

const SortableSlideCard: React.FC<SortableSlideCardProps> = ({
  slide,
  index,
  isActive,
  onSelect
}) => {
  const readiness = describeSlideReadiness(slide)
  const {
    ref,
    handleRef,
    isDragging
  } = useSortable({
    id: slide.metadata.studio.slideId,
    index,
    collisionDetector: closestCenter
  })

  return (
    <div
      ref={ref}
      className={`min-w-0 rounded-2xl border transition ${
        isActive
          ? "border-slate-900 bg-slate-950 text-white shadow-sm"
          : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
      }`}
      data-testid="presentation-studio-slide-card"
      data-slide-id={slide.metadata.studio.slideId}
      style={{ opacity: isDragging ? 0.5 : 1 }}
    >
      <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-3 px-3 py-4">
        <button
          ref={handleRef}
          aria-label={`Drag to reorder slide ${index + 1}`}
          className={`mt-1 flex h-8 w-8 items-center justify-center rounded-lg border transition ${
            isActive
              ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
              : "border-slate-200 bg-slate-50 text-slate-500 hover:border-slate-300 hover:text-slate-700"
          } cursor-grab active:cursor-grabbing`}
          data-testid="presentation-studio-slide-handle"
          title={`Drag to reorder slide ${index + 1}`}
          type="button"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        <button
          className="min-w-0 text-left"
          onClick={() => onSelect(slide.metadata.studio.slideId)}
          type="button"
        >
          <div className="flex items-center justify-between gap-2">
            <span
              className={`text-xs font-semibold uppercase tracking-[0.16em] ${
                isActive ? "text-slate-300" : "text-slate-500"
              }`}
            >
              Slide {index + 1}
            </span>
            <Badge
              className={isActive ? "bg-white/10 text-white" : ""}
              size="sm"
              variant={isActive ? "info" : "secondary"}
            >
              {slide.layout}
            </Badge>
          </div>
          <div
            className={`mt-3 text-sm font-semibold ${
              isActive ? "text-white" : "text-slate-900"
            }`}
          >
            {slide.title || "Untitled slide"}
          </div>
          <div
            className={`mt-2 line-clamp-2 text-xs ${
              isActive ? "text-slate-200" : "text-slate-500"
            }`}
          >
            {slide.content || "Add concise on-slide copy for this step of the story."}
          </div>
          <div
            className={`mt-2 line-clamp-2 text-[11px] ${
              isActive ? "text-slate-300" : "text-slate-500"
            }`}
          >
            {readiness.isReady
              ? `${readiness.transitionLabel} transition · ${readiness.effectiveTiming}`
              : readiness.issues[0]}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge size="sm" variant={readiness.isReady ? "success" : "warning"}>
              {readiness.summaryLabel}
            </Badge>
            <Badge size="sm" variant="secondary">
              {readiness.transitionLabel}
            </Badge>
            <PresentationStudioStatusBadge status={slide.metadata.studio.audio.status} />
            <PresentationStudioStatusBadge status={slide.metadata.studio.image.status} />
          </div>
        </button>
      </div>
    </div>
  )
}

export const SlideRail: React.FC = () => {
  const slides = usePresentationStudioStore((state) => state.slides)
  const selectedSlideId = usePresentationStudioStore((state) => state.selectedSlideId)
  const selectSlide = usePresentationStudioStore((state) => state.selectSlide)
  const addSlide = usePresentationStudioStore((state) => state.addSlide)
  const duplicateSlide = usePresentationStudioStore((state) => state.duplicateSlide)
  const removeSlide = usePresentationStudioStore((state) => state.removeSlide)
  const moveSlide = usePresentationStudioStore((state) => state.moveSlide)
  const reorderSlides = usePresentationStudioStore((state) => state.reorderSlides)
  const selectedSlide =
    slides.find((slide) => slide.metadata.studio.slideId === selectedSlideId) || null
  const selectedIndex = selectedSlide
    ? slides.findIndex(
        (slide) => slide.metadata.studio.slideId === selectedSlide.metadata.studio.slideId
      )
    : -1
  const deckReadiness = deriveDeckReadiness(slides)
  const readySlideCount = deckReadiness.readySlides
  const needsAttentionCount = slides.length - readySlideCount
  const canMoveEarlier = selectedIndex > 0
  const canMoveLater = selectedIndex > -1 && selectedIndex < slides.length - 1

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      if (event.canceled) {
        return
      }

      const sourceId = event.operation.source?.id
      const targetId = event.operation.target?.id
      if (!sourceId || !targetId || sourceId === targetId) {
        return
      }

      const fromIndex = slides.findIndex(
        (slide) => slide.metadata.studio.slideId === sourceId
      )
      const toIndex = slides.findIndex((slide) => slide.metadata.studio.slideId === targetId)
      if (fromIndex === -1 || toIndex === -1) {
        return
      }

      reorderSlides(fromIndex, toIndex)
    },
    [reorderSlides, slides]
  )

  return (
    <aside
      className="flex min-h-[320px] min-w-0 flex-col gap-4 overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      data-testid="presentation-studio-slide-rail"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-900">Slides</h2>
            <Badge size="sm" variant="secondary">
              {slides.length} total
            </Badge>
            <Badge size="sm" variant="success">
              {readySlideCount} ready
            </Badge>
            <Badge size="sm" variant="warning">
              {needsAttentionCount} need attention
            </Badge>
          </div>
          <p className="text-sm text-slate-500">Arrange and edit your sequence.</p>
        </div>
        <button
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
          onClick={() => addSlide()}
          type="button"
        >
          Add slide
        </button>
      </div>

      {selectedSlide ? (
        <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Selected slide
            </p>
            <p className="truncate text-sm font-semibold text-slate-900">
              {selectedSlide.title || "Untitled slide"}
            </p>
          </div>
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            disabled={!canMoveEarlier}
            onClick={() => moveSlide(selectedSlide.metadata.studio.slideId, "earlier")}
            type="button"
          >
            Move earlier
          </button>
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            disabled={!canMoveLater}
            onClick={() => moveSlide(selectedSlide.metadata.studio.slideId, "later")}
            type="button"
          >
            Move later
          </button>
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
            onClick={() => duplicateSlide(selectedSlide.metadata.studio.slideId)}
            type="button"
          >
            Duplicate slide
          </button>
          <button
            className="rounded-lg border border-rose-200 px-3 py-2 text-sm font-medium text-rose-700 transition hover:border-rose-300 hover:text-rose-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            disabled={slides.length <= 1}
            onClick={() => removeSlide(selectedSlide.metadata.studio.slideId)}
            type="button"
          >
            Delete slide
          </button>
        </div>
      ) : null}

      <DragDropProvider onDragEnd={handleDragEnd}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
          {slides.map((slide, index) => (
            <SortableSlideCard
              key={slide.metadata.studio.slideId}
              index={index}
              isActive={slide.metadata.studio.slideId === selectedSlideId}
              onSelect={selectSlide}
              slide={slide}
            />
          ))}
        </div>
      </DragDropProvider>
    </aside>
  )
}
