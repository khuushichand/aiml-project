export type ContentLayout = {
  minHeightEm: number
  capped: boolean
}

export function getContentLayout(contentLength: number): ContentLayout {
  if (contentLength < 500) return { minHeightEm: 6, capped: false }
  if (contentLength < 5000) return { minHeightEm: 10, capped: true }
  return { minHeightEm: 14, capped: true }
}

