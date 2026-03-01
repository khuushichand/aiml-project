export type DiagnosticsSummaryStatus = "warning" | "busy" | "ready"

export type DiagnosticsSummaryInput = {
  showOffline: boolean
  showUnsupported: boolean
  isGenerating: boolean
}

export type DiagnosticsSummary = {
  status: DiagnosticsSummaryStatus
}

export function buildDiagnosticsSummary(
  input: DiagnosticsSummaryInput
): DiagnosticsSummary {
  if (input.showOffline || input.showUnsupported) {
    return { status: "warning" }
  }
  if (input.isGenerating) {
    return { status: "busy" }
  }
  return { status: "ready" }
}
