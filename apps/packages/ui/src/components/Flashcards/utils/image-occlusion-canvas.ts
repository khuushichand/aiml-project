export interface ImageOcclusionRenderableRegion {
  id: string
  label: string
  x: number
  y: number
  width: number
  height: number
}

type LoadedImage = {
  image: CanvasImageSource
  width: number
  height: number
  cleanup?: () => void
}

type CanvasLike = {
  width: number
  height: number
  getContext: (contextId: "2d") => CanvasRenderingContext2DLike | null
}

type CanvasRenderingContext2DLike = {
  fillStyle: string | CanvasGradient | CanvasPattern
  strokeStyle: string | CanvasGradient | CanvasPattern
  lineWidth: number
  drawImage: (image: CanvasImageSource, dx: number, dy: number, dw: number, dh: number) => void
  fillRect: (x: number, y: number, width: number, height: number) => void
  strokeRect: (x: number, y: number, width: number, height: number) => void
  save: () => void
  restore: () => void
}

export interface ImageOcclusionCanvasDeps {
  loadImage?: (file: File) => Promise<LoadedImage>
  createCanvas?: (width: number, height: number) => CanvasLike
  canvasToBlob?: (canvas: CanvasLike, mimeType: string, quality: number) => Promise<Blob>
}

export interface GenerateImageOcclusionAssetsOptions {
  maxEdgePx?: number
  mimeType?: string
  quality?: number
  deps?: ImageOcclusionCanvasDeps
}

export interface GeneratedImageOcclusionAssets {
  source: {
    blob: Blob
    width: number
    height: number
    mimeType: string
  }
  regions: Array<{
    regionId: string
    promptBlob: Blob
    answerBlob: Blob
    width: number
    height: number
    mimeType: string
  }>
}

const DEFAULT_MAX_EDGE_PX = 1600
const DEFAULT_MIME_TYPE = "image/webp"
const DEFAULT_QUALITY = 0.92

const scaleDimensions = (
  width: number,
  height: number,
  maxEdgePx: number
): { width: number; height: number } => {
  const normalizedWidth = Math.max(1, Math.round(width))
  const normalizedHeight = Math.max(1, Math.round(height))
  const longestEdge = Math.max(normalizedWidth, normalizedHeight)
  if (longestEdge <= maxEdgePx) {
    return {
      width: normalizedWidth,
      height: normalizedHeight
    }
  }

  const scale = maxEdgePx / longestEdge
  return {
    width: Math.max(1, Math.round(normalizedWidth * scale)),
    height: Math.max(1, Math.round(normalizedHeight * scale))
  }
}

const toPixelRect = (
  region: Pick<ImageOcclusionRenderableRegion, "x" | "y" | "width" | "height">,
  dimensions: { width: number; height: number }
) => ({
  x: Math.round(region.x * dimensions.width),
  y: Math.round(region.y * dimensions.height),
  width: Math.round(region.width * dimensions.width),
  height: Math.round(region.height * dimensions.height)
})

const defaultLoadImage = async (file: File): Promise<LoadedImage> => {
  if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
    throw new Error("Object URLs are not supported in this environment.")
  }

  const objectUrl = URL.createObjectURL(file)
  try {
    const loaded = await new Promise<LoadedImage>((resolve, reject) => {
      const image = new Image()
      image.onload = () =>
        resolve({
          image,
          width: image.naturalWidth || image.width,
          height: image.naturalHeight || image.height
        })
      image.onerror = () => reject(new Error("Failed to decode occlusion source image."))
      image.src = objectUrl
    })
    return {
      ...loaded,
      cleanup: () => URL.revokeObjectURL(objectUrl)
    }
  } catch (error) {
    URL.revokeObjectURL(objectUrl)
    throw error
  }
}

const defaultCreateCanvas = (width: number, height: number): CanvasLike => {
  if (typeof document === "undefined") {
    throw new Error("Canvas rendering is not supported in this environment.")
  }
  const canvas = document.createElement("canvas")
  canvas.width = width
  canvas.height = height
  return canvas
}

const defaultCanvasToBlob = async (
  canvas: CanvasLike,
  mimeType: string,
  quality: number
): Promise<Blob> => {
  const htmlCanvas = canvas as HTMLCanvasElement
  if (typeof htmlCanvas.toBlob !== "function") {
    throw new Error("Canvas encoding is not supported in this environment.")
  }
  return await new Promise<Blob>((resolve, reject) => {
    htmlCanvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob)
          return
        }
        reject(new Error("Canvas encoding returned an empty blob."))
      },
      mimeType,
      quality
    )
  })
}

const getContext = (canvas: CanvasLike): CanvasRenderingContext2DLike => {
  const context = canvas.getContext("2d")
  if (!context) {
    throw new Error("Failed to acquire a 2D canvas context.")
  }
  return context
}

const drawBaseImage = (
  context: CanvasRenderingContext2DLike,
  image: CanvasImageSource,
  dimensions: { width: number; height: number }
) => {
  context.drawImage(image, 0, 0, dimensions.width, dimensions.height)
}

const renderSourceBlob = async (
  image: CanvasImageSource,
  dimensions: { width: number; height: number },
  mimeType: string,
  quality: number,
  deps: Required<ImageOcclusionCanvasDeps>
): Promise<Blob> => {
  const canvas = deps.createCanvas(dimensions.width, dimensions.height)
  const context = getContext(canvas)
  drawBaseImage(context, image, dimensions)
  return await deps.canvasToBlob(canvas, mimeType, quality)
}

const renderRegionVariantBlob = async (
  image: CanvasImageSource,
  region: Pick<ImageOcclusionRenderableRegion, "x" | "y" | "width" | "height">,
  dimensions: { width: number; height: number },
  variant: "prompt" | "answer",
  mimeType: string,
  quality: number,
  deps: Required<ImageOcclusionCanvasDeps>
): Promise<Blob> => {
  const canvas = deps.createCanvas(dimensions.width, dimensions.height)
  const context = getContext(canvas)
  const pixelRect = toPixelRect(region, dimensions)

  drawBaseImage(context, image, dimensions)
  context.save()
  if (variant === "prompt") {
    context.fillStyle = "rgba(15, 23, 42, 0.78)"
    context.strokeStyle = "rgba(255, 255, 255, 0.92)"
    context.lineWidth = 3
  } else {
    context.fillStyle = "rgba(250, 204, 21, 0.22)"
    context.strokeStyle = "rgba(250, 204, 21, 0.95)"
    context.lineWidth = 4
  }
  context.fillRect(pixelRect.x, pixelRect.y, pixelRect.width, pixelRect.height)
  context.strokeRect(pixelRect.x, pixelRect.y, pixelRect.width, pixelRect.height)
  context.restore()

  return await deps.canvasToBlob(canvas, mimeType, quality)
}

export async function generateImageOcclusionAssets(
  sourceFile: File,
  regions: ImageOcclusionRenderableRegion[],
  options: GenerateImageOcclusionAssetsOptions = {}
): Promise<GeneratedImageOcclusionAssets> {
  const maxEdgePx = options.maxEdgePx ?? DEFAULT_MAX_EDGE_PX
  const mimeType = options.mimeType ?? DEFAULT_MIME_TYPE
  const quality = options.quality ?? DEFAULT_QUALITY
  const deps: Required<ImageOcclusionCanvasDeps> = {
    loadImage: options.deps?.loadImage ?? defaultLoadImage,
    createCanvas: options.deps?.createCanvas ?? defaultCreateCanvas,
    canvasToBlob: options.deps?.canvasToBlob ?? defaultCanvasToBlob
  }

  const loaded = await deps.loadImage(sourceFile)
  const dimensions = scaleDimensions(loaded.width, loaded.height, maxEdgePx)

  try {
    const sourceBlob = await renderSourceBlob(
      loaded.image,
      dimensions,
      mimeType,
      quality,
      deps
    )

    const derivedRegions = await Promise.all(
      regions.map(async (region) => ({
        regionId: region.id,
        promptBlob: await renderRegionVariantBlob(
          loaded.image,
          region,
          dimensions,
          "prompt",
          mimeType,
          quality,
          deps
        ),
        answerBlob: await renderRegionVariantBlob(
          loaded.image,
          region,
          dimensions,
          "answer",
          mimeType,
          quality,
          deps
        ),
        width: dimensions.width,
        height: dimensions.height,
        mimeType
      }))
    )

    return {
      source: {
        blob: sourceBlob,
        width: dimensions.width,
        height: dimensions.height,
        mimeType
      },
      regions: derivedRegions
    }
  } finally {
    loaded.cleanup?.()
  }
}
