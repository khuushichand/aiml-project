export type ContentFilterProgress = {
  completed: number
  total: number
  running: boolean
}

export const IDLE_CONTENT_FILTER_PROGRESS: ContentFilterProgress = {
  completed: 0,
  total: 0,
  running: false
}

export const toProgressLabel = (progress: ContentFilterProgress): string => {
  const total = Math.max(progress.total, 0)
  const completed = Math.min(Math.max(progress.completed, 0), total)
  return `${completed}/${total}`
}

