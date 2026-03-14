import type { PresentationStudioEditorSlide } from "@/store/presentation-studio"

type SlideReadinessDescription = {
  isReady: boolean
  summaryLabel: "Ready to render" | "Needs attention"
  issues: string[]
  narrationTiming: string
  effectiveTiming: string
  transitionLabel: string
}

type DeckReadinessSummary = {
  readySlides: number
  slidesMissingImages: number
  slidesMissingNarration: number
  slidesWithStaleNarration: number
  totalNarrationDuration: string
  totalDeckDuration: string
}

const formatSeconds = (value: number): string => `${value}s`
const transitionLabels = {
  fade: "Fade",
  cut: "Cut",
  wipe: "Wipe",
  zoom: "Zoom"
} as const

export const formatNarrationDuration = (durationMs: number | null | undefined): string => {
  if (typeof durationMs !== "number" || !Number.isFinite(durationMs) || durationMs <= 0) {
    return "Unknown until audio is generated"
  }

  const totalSeconds = Math.round(durationMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60

  if (minutes <= 0) {
    return formatSeconds(totalSeconds)
  }

  return `${minutes}m ${formatSeconds(seconds)}`
}

export const getEffectiveSlideDurationMs = (
  slide: PresentationStudioEditorSlide
): number | null => {
  if (
    slide.metadata.studio.timing_mode === "manual" &&
    typeof slide.metadata.studio.manual_duration_ms === "number" &&
    slide.metadata.studio.manual_duration_ms > 0
  ) {
    return slide.metadata.studio.manual_duration_ms
  }

  return typeof slide.metadata.studio.audio.duration_ms === "number" &&
    slide.metadata.studio.audio.duration_ms > 0
    ? slide.metadata.studio.audio.duration_ms
    : null
}

export const formatTransitionLabel = (
  transition: PresentationStudioEditorSlide["metadata"]["studio"]["transition"]
): string => transitionLabels[transition] || "Fade"

export const describeSlideReadiness = (
  slide: PresentationStudioEditorSlide
): SlideReadinessDescription => {
  const issues: string[] = []
  const audioStatus = slide.metadata.studio.audio.status
  const imageStatus = slide.metadata.studio.image.status

  if (audioStatus === "missing") {
    issues.push("Generate narration audio to estimate timing and publish this slide.")
  } else if (audioStatus === "stale") {
    issues.push("Refresh narration to match the latest script changes.")
  } else if (audioStatus === "failed") {
    issues.push("Retry narration generation after the previous audio run failed.")
  } else if (audioStatus === "generating") {
    issues.push("Narration is still generating for this slide.")
  }

  if (imageStatus === "missing") {
    issues.push("Add or generate a slide image before publishing.")
  } else if (imageStatus === "failed") {
    issues.push("Retry image generation or upload a replacement image.")
  } else if (imageStatus === "generating") {
    issues.push("Image generation is still in progress for this slide.")
  }

  if (
    slide.metadata.studio.timing_mode === "manual" &&
    (!slide.metadata.studio.manual_duration_ms || slide.metadata.studio.manual_duration_ms <= 0)
  ) {
    issues.push("Set a manual duration or switch back to auto timing.")
  }

  const isReady = issues.length === 0
  const effectiveDurationMs = getEffectiveSlideDurationMs(slide)

  return {
    isReady,
    summaryLabel: isReady ? "Ready to render" : "Needs attention",
    issues,
    narrationTiming: formatNarrationDuration(slide.metadata.studio.audio.duration_ms),
    effectiveTiming: formatNarrationDuration(effectiveDurationMs),
    transitionLabel: formatTransitionLabel(slide.metadata.studio.transition)
  }
}

export const deriveDeckReadiness = (
  slides: PresentationStudioEditorSlide[]
): DeckReadinessSummary => {
  const summary = slides.reduce(
    (accumulator, slide) => {
      const readiness = describeSlideReadiness(slide)
      if (readiness.isReady) {
        accumulator.readySlides += 1
      }
      if (slide.metadata.studio.image.status !== "ready") {
        accumulator.slidesMissingImages += 1
      }
      if (slide.metadata.studio.audio.status === "missing") {
        accumulator.slidesMissingNarration += 1
      }
      if (slide.metadata.studio.audio.status === "stale") {
        accumulator.slidesWithStaleNarration += 1
      }
      if (
        typeof slide.metadata.studio.audio.duration_ms === "number" &&
        slide.metadata.studio.audio.duration_ms > 0
      ) {
        accumulator.totalNarrationMs += slide.metadata.studio.audio.duration_ms
      }
      const effectiveDurationMs = getEffectiveSlideDurationMs(slide)
      if (typeof effectiveDurationMs === "number" && effectiveDurationMs > 0) {
        accumulator.totalDeckMs += effectiveDurationMs
      }
      return accumulator
    },
    {
      readySlides: 0,
      slidesMissingImages: 0,
      slidesMissingNarration: 0,
      slidesWithStaleNarration: 0,
      totalNarrationMs: 0,
      totalDeckMs: 0
    }
  )

  return {
    readySlides: summary.readySlides,
    slidesMissingImages: summary.slidesMissingImages,
    slidesMissingNarration: summary.slidesMissingNarration,
    slidesWithStaleNarration: summary.slidesWithStaleNarration,
    totalNarrationDuration: formatNarrationDuration(summary.totalNarrationMs || null),
    totalDeckDuration: formatNarrationDuration(summary.totalDeckMs || null)
  }
}
