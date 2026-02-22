type ErrorWithStatus = {
  status?: number
}

export const getErrorStatus = (error: unknown): number | undefined => {
  if (!error || typeof error !== "object") {
    return undefined
  }
  const status = (error as ErrorWithStatus).status
  return typeof status === "number" ? status : undefined
}

export const isNotFoundError = (error: unknown): boolean =>
  getErrorStatus(error) === 404

export const shouldRetryDocumentWorkspaceQuery = (
  failureCount: number,
  error: unknown,
  maxRetries: number
): boolean => {
  if (isNotFoundError(error)) {
    return false
  }
  return failureCount < maxRetries
}
