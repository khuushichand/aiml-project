import { describe, expect, it } from "vitest"

import { generateImageOcclusionAssets, type ImageOcclusionCanvasDeps } from "../image-occlusion-canvas"
import type { ImageOcclusionRegion } from "../../tabs/ImageOcclusionPanel"

type RecordedOperation = {
  type: string
  args: number[]
  fillStyle?: string
  strokeStyle?: string
  lineWidth?: number
}

type RecordedCanvas = {
  width: number
  height: number
  operations: RecordedOperation[]
  getContext: () => any
}

const createFakeCanvasDeps = (
  imageDimensions: { width: number; height: number }
): ImageOcclusionCanvasDeps => ({
  loadImage: async () => ({
    image: ({
      width: imageDimensions.width,
      height: imageDimensions.height
    } as unknown) as CanvasImageSource,
    width: imageDimensions.width,
    height: imageDimensions.height
  }),
  createCanvas: (width, height) => {
    const operations: RecordedOperation[] = []
    const stateStack: Array<{
      fillStyle: string
      strokeStyle: string
      lineWidth: number
    }> = []
    const context = {
      fillStyle: "",
      strokeStyle: "",
      lineWidth: 1,
      save() {
        stateStack.push({
          fillStyle: this.fillStyle,
          strokeStyle: this.strokeStyle,
          lineWidth: this.lineWidth
        })
      },
      restore() {
        const next = stateStack.pop()
        if (!next) return
        this.fillStyle = next.fillStyle
        this.strokeStyle = next.strokeStyle
        this.lineWidth = next.lineWidth
      },
      drawImage(_image: unknown, ...args: number[]) {
        operations.push({ type: "drawImage", args })
      },
      fillRect(...args: number[]) {
        operations.push({
          type: "fillRect",
          args,
          fillStyle: this.fillStyle
        })
      },
      strokeRect(...args: number[]) {
        operations.push({
          type: "strokeRect",
          args,
          strokeStyle: this.strokeStyle,
          lineWidth: this.lineWidth
        })
      }
    }
    return {
      width,
      height,
      operations,
      getContext: () => context
    } satisfies RecordedCanvas
  },
  canvasToBlob: async (canvas, mimeType) =>
    new Blob(
      [
        JSON.stringify({
          width: canvas.width,
          height: canvas.height,
          operations: (canvas as RecordedCanvas).operations
        })
      ],
      { type: mimeType }
    )
})

const readBlobJson = async (blob: Blob) => JSON.parse(await blob.text())

const regions: ImageOcclusionRegion[] = [
  {
    id: "region-1",
    label: "A",
    x: 0.1,
    y: 0.2,
    width: 0.3,
    height: 0.4
  },
  {
    id: "region-2",
    label: "B",
    x: 0.55,
    y: 0.15,
    width: 0.2,
    height: 0.25
  }
]

describe("generateImageOcclusionAssets", () => {
  it("returns prompt and answer blobs for one region", async () => {
    const result = await generateImageOcclusionAssets(
      new File(["binary"], "diagram.png", { type: "image/png" }),
      [regions[0]],
      {
        deps: createFakeCanvasDeps({ width: 1000, height: 500 })
      }
    )

    expect(result.source.width).toBe(1000)
    expect(result.source.height).toBe(500)
    expect(result.regions).toHaveLength(1)

    const prompt = await readBlobJson(result.regions[0].promptBlob)
    const answer = await readBlobJson(result.regions[0].answerBlob)

    expect(prompt.operations).toEqual([
      { type: "drawImage", args: [0, 0, 1000, 500] },
      {
        type: "fillRect",
        args: [100, 100, 300, 200],
        fillStyle: "rgba(15, 23, 42, 0.78)"
      },
      {
        type: "strokeRect",
        args: [100, 100, 300, 200],
        strokeStyle: "rgba(255, 255, 255, 0.92)",
        lineWidth: 3
      }
    ])
    expect(answer.operations).toEqual([
      { type: "drawImage", args: [0, 0, 1000, 500] },
      {
        type: "fillRect",
        args: [100, 100, 300, 200],
        fillStyle: "rgba(250, 204, 21, 0.22)"
      },
      {
        type: "strokeRect",
        args: [100, 100, 300, 200],
        strokeStyle: "rgba(250, 204, 21, 0.95)",
        lineWidth: 4
      }
    ])
  })

  it("processes two regions deterministically in source order", async () => {
    const result = await generateImageOcclusionAssets(
      new File(["binary"], "diagram.png", { type: "image/png" }),
      regions,
      {
        deps: createFakeCanvasDeps({ width: 1200, height: 800 })
      }
    )

    expect(result.regions.map((item) => item.regionId)).toEqual(["region-1", "region-2"])

    const secondPrompt = await readBlobJson(result.regions[1].promptBlob)
    expect(secondPrompt.operations[1]).toEqual({
      type: "fillRect",
      args: [660, 120, 240, 200],
      fillStyle: "rgba(15, 23, 42, 0.78)"
    })
  })

  it("scales oversize sources down to the configured max edge", async () => {
    const result = await generateImageOcclusionAssets(
      new File(["binary"], "lecture.png", { type: "image/png" }),
      [regions[0]],
      {
        maxEdgePx: 1600,
        deps: createFakeCanvasDeps({ width: 3200, height: 1600 })
      }
    )

    expect(result.source.width).toBe(1600)
    expect(result.source.height).toBe(800)

    const prompt = await readBlobJson(result.regions[0].promptBlob)
    expect(prompt.operations[1]).toEqual({
      type: "fillRect",
      args: [160, 160, 480, 320],
      fillStyle: "rgba(15, 23, 42, 0.78)"
    })
  })
})
