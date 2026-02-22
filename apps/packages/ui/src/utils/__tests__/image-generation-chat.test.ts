import { describe, expect, it } from "vitest"
import {
  buildImageGenerationEventMirrorContent,
  isImageGenerationMessageType,
  normalizeImageGenerationVariantBundle,
  parseImageGenerationEventMirrorContent,
  resolveImageGenerationEventId,
  resolveImageGenerationVariantId,
  resolveImageGenerationEventSyncMode,
  resolveImageGenerationMetadata
} from "@/utils/image-generation-chat"

describe("image-generation-chat helpers", () => {
  it("recognizes image generation message types", () => {
    expect(isImageGenerationMessageType("image-generation:user")).toBe(true)
    expect(isImageGenerationMessageType("image-generation:assistant")).toBe(true)
    expect(isImageGenerationMessageType("character:greeting")).toBe(false)
    expect(isImageGenerationMessageType(undefined)).toBe(false)
  })

  it("extracts reusable request metadata from generation info", () => {
    const metadata = resolveImageGenerationMetadata({
      image_generation: {
        request: {
          prompt: "portrait of Lana",
          backend: "tldw_server-Flux-Klein",
          width: 768,
          height: 1024,
          format: "png",
          extraParams: { tiling: false }
        },
        source: "generate-modal",
        promptMode: "expression",
        createdAt: 123,
        refine: {
          model: "deepseek-chat",
          latencyMs: 212,
          diffStats: {
            baselineSegments: 5,
            candidateSegments: 6,
            sharedSegments: 4,
            overlapRatio: 0.66,
            addedCount: 2,
            removedCount: 1
          }
        }
      }
    })

    expect(metadata).toBeTruthy()
    expect(metadata?.request.prompt).toBe("portrait of Lana")
    expect(metadata?.request.backend).toBe("tldw_server-Flux-Klein")
    expect(metadata?.request.width).toBe(768)
    expect(metadata?.source).toBe("generate-modal")
    expect(metadata?.promptMode).toBe("expression")
    expect(metadata?.refine?.model).toBe("deepseek-chat")
    expect(metadata?.refine?.diffStats.addedCount).toBe(2)
  })

  it("supports legacy refine metadata fields", () => {
    const metadata = resolveImageGenerationMetadata({
      image_generation: {
        request: {
          prompt: "scene prompt",
          backend: "image-backend"
        },
        refine_model: "gpt-4o-mini",
        refine_latency_ms: 95,
        diff_stats: {
          baselineSegments: 2,
          candidateSegments: 3,
          sharedSegments: 1,
          overlapRatio: 0.33,
          addedCount: 2,
          removedCount: 1
        }
      }
    })

    expect(metadata?.refine?.model).toBe("gpt-4o-mini")
    expect(metadata?.refine?.latencyMs).toBe(95)
    expect(metadata?.refine?.diffStats.removedCount).toBe(1)
  })

  it("resolves sync mode with request override precedence", () => {
    expect(
      resolveImageGenerationEventSyncMode({
        requestPolicy: "on",
        chatMode: "off",
        globalMode: "off"
      })
    ).toBe("on")
    expect(
      resolveImageGenerationEventSyncMode({
        requestPolicy: "inherit",
        chatMode: "on",
        globalMode: "off"
      })
    ).toBe("on")
    expect(
      resolveImageGenerationEventSyncMode({
        requestPolicy: "inherit",
        chatMode: "off",
        globalMode: "on"
      })
    ).toBe("off")
  })

  it("serializes and parses mirrored image event payload content", () => {
    const content = buildImageGenerationEventMirrorContent({
      kind: "image_generation_event",
      version: 1,
      eventId: "evt-42",
      request: {
        prompt: "portrait shot",
        backend: "flux",
        width: 768,
        height: 1024
      },
      source: "generate-modal",
      imageDataUrl: "data:image/png;base64,abc123"
    })
    const parsed = parseImageGenerationEventMirrorContent(content)
    expect(parsed).toBeTruthy()
    expect(parsed?.eventId).toBe("evt-42")
    expect(parsed?.request.backend).toBe("flux")
    expect(parsed?.source).toBe("generate-modal")
    expect(parsed?.imageDataUrl).toBe("data:image/png;base64,abc123")
  })

  it("normalizes single-event image metadata with stable event and variant ids", () => {
    const normalized = normalizeImageGenerationVariantBundle({
      messageId: "assistant-image-1",
      messageGenerationInfo: {
        image_generation: {
          request: {
            prompt: "sunlit city skyline",
            backend: "comfyui"
          }
        }
      },
      variants: [],
      activeVariantIndex: 0,
      hasVisibleVariant: true
    })

    const imageGeneration = (normalized.generationInfo as any)?.image_generation
    expect(normalized.eventId).toBe("assistant-image-1")
    expect(normalized.variantCount).toBe(1)
    expect(imageGeneration?.event_id).toBe("assistant-image-1")
    expect(imageGeneration?.variant_id).toBe("assistant-image-1")
    expect(imageGeneration?.variant_index).toBe(0)
    expect(imageGeneration?.variant_count).toBe(1)
    expect(imageGeneration?.active_variant_index).toBe(0)
    expect(imageGeneration?.is_kept).toBe(true)
  })

  it("normalizes grouped variants and keeps a shared event id", () => {
    const baseVariants = [
      {
        id: "variant-a",
        generationInfo: {
          image_generation: {
            request: { prompt: "scene", backend: "comfyui" }
          }
        }
      },
      {
        id: "variant-b",
        generationInfo: {
          image_generation: {
            request: { prompt: "scene", backend: "comfyui" },
            event_id: "event-stable"
          }
        }
      }
    ]

    const normalized = normalizeImageGenerationVariantBundle({
      messageId: "assistant-image-2",
      messageGenerationInfo: baseVariants[1].generationInfo,
      variants: baseVariants,
      activeVariantIndex: 1
    })

    expect(normalized.eventId).toBe("event-stable")
    expect(normalized.variantCount).toBe(2)
    const firstImageGeneration = (normalized.variants[0] as any)?.generationInfo
      ?.image_generation
    const secondImageGeneration = (normalized.variants[1] as any)?.generationInfo
      ?.image_generation
    expect(firstImageGeneration?.event_id).toBe("event-stable")
    expect(secondImageGeneration?.event_id).toBe("event-stable")
    expect(firstImageGeneration?.variant_index).toBe(0)
    expect(secondImageGeneration?.variant_index).toBe(1)
    expect(firstImageGeneration?.active_variant_index).toBe(1)
    expect(secondImageGeneration?.active_variant_index).toBe(1)
    expect(firstImageGeneration?.is_kept).toBe(false)
    expect(secondImageGeneration?.is_kept).toBe(true)

    expect(
      resolveImageGenerationEventId({
        messageId: "fallback-event",
        variants: normalized.variants
      })
    ).toBe("event-stable")
    expect(
      resolveImageGenerationVariantId({
        eventId: "event-stable",
        variantIndex: 1,
        generationInfo: (normalized.variants[1] as any)?.generationInfo
      })
    ).toBe("variant-b")
  })
})
