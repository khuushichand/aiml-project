export const getWorkspaceSourcesLocationLabel = (
  isMobile: boolean
): string => (isMobile ? "Sources tab" : "Sources pane")

export const getWorkspaceChatNoSourcesHint = (
  isMobile: boolean
): string =>
  `Select sources from the ${getWorkspaceSourcesLocationLabel(isMobile)}, then ask questions`

export const getWorkspaceStudioNoSourcesHint = (
  isMobile: boolean
): string =>
  `Select sources from the ${getWorkspaceSourcesLocationLabel(isMobile)} to enable generation`
