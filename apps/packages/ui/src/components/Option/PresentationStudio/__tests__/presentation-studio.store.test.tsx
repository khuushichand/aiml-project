import { beforeEach, describe, expect, it } from "vitest"

import { usePresentationStudioStore } from "@/store/presentation-studio"

const sampleProject = {
  id: "pres-123",
  title: "Deck",
  description: null,
  theme: "black",
  marp_theme: null,
  template_id: null,
  settings: null,
  studio_data: { origin: "blank" },
  slides: [
    {
      order: 0,
      layout: "title",
      title: "Intro",
      content: "Welcome",
      speaker_notes: "Original narration",
      metadata: {
        studio: {
          slideId: "slide-1",
          audio: {
            status: "ready",
            asset_ref: "output:1"
          }
        }
      }
    }
  ],
  custom_css: null,
  source_type: "manual",
  source_ref: null,
  source_query: null,
  created_at: "2026-03-13T00:00:00Z",
  last_modified: "2026-03-13T00:00:00Z",
  deleted: false,
  client_id: "1",
  version: 1
} as const

describe("presentation studio store", () => {
  beforeEach(() => {
    usePresentationStudioStore.getState().reset()
  })

  it("marks audio stale when speaker_notes change", () => {
    const store = usePresentationStudioStore.getState()
    store.loadProject(sampleProject)
    store.updateSlide("slide-1", { speaker_notes: "New narration" })

    expect(usePresentationStudioStore.getState().slides[0]?.metadata?.studio?.audio?.status).toBe(
      "stale"
    )
  })
})
