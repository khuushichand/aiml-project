import React from "react"

export type BackendUnavailableRecoveryDetails = {
  title?: React.ReactNode
  message?: React.ReactNode
  fixHint?: React.ReactNode
  subtype?: string
  method?: string
  path?: string
  serverUrl?: string
  status?: number
  rawMessage?: string
  source?: string
  recentRequestError?: unknown
  diagnostics?: unknown
}

type BackendUnavailableRecoveryProps = {
  details?: BackendUnavailableRecoveryDetails
  onRetry: () => void
  onReload: () => void
  onOpenDiagnostics: () => void
  onOpenSettings: () => void
}

const DEFAULT_TITLE = "Can't reach your tldw server right now."
const DEFAULT_MESSAGE =
  "Check that your server is running and accessible. Try again, reload the page, or open Health & diagnostics for more details."

const actionButtonClassName =
  "inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-bg"

const primaryActionClassName =
  "bg-primary text-white hover:bg-primaryStrong"

const secondaryActionClassName =
  "border border-border bg-surface text-text hover:bg-surface2"

const informationRowClassName =
  "grid gap-1 rounded-2xl border border-border/70 bg-surface2/60 p-3"

const formatStructuredValue = (value: unknown): React.ReactNode => {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value === "string") {
    return value
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }

  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const hasDiagnostics = (details?: BackendUnavailableRecoveryDetails): boolean =>
  Boolean(
    details &&
      (details.method ||
        details.path ||
        details.serverUrl ||
        details.status !== undefined ||
        details.rawMessage ||
        details.source ||
        details.recentRequestError ||
        details.diagnostics)
  )

export const BackendUnavailableRecovery: React.FC<
  BackendUnavailableRecoveryProps
> = ({
  details,
  onRetry,
  onReload,
  onOpenDiagnostics,
  onOpenSettings
}) => {
  const title = details?.title ?? DEFAULT_TITLE
  const message = details?.message ?? DEFAULT_MESSAGE
  const fixHint = details?.fixHint
  const showDiagnostics = hasDiagnostics(details)

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 py-10 text-text">
      <section
        className="w-full max-w-3xl rounded-3xl border border-border/80 bg-surface p-8 shadow-card"
        aria-labelledby="backend-unavailable-recovery-title"
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-subtle">
              Connection issue
            </p>
            <h1
              id="backend-unavailable-recovery-title"
              className="text-3xl font-semibold tracking-tight text-text"
            >
              {title}
            </h1>
            <p className="max-w-2xl text-sm leading-6 text-text-muted">
              {message}
            </p>
            {fixHint ? (
              <p
                className="max-w-2xl rounded-xl border border-border/60 bg-surface2/40 px-4 py-3 text-sm leading-6 text-text-muted"
                data-testid="backend-recovery-fix-hint"
              >
                <span className="font-medium text-text">How to fix: </span>
                {fixHint}
              </p>
            ) : null}
          </div>

          {showDiagnostics ? (
            <section
              aria-label="Diagnostics"
              className="space-y-3 rounded-2xl border border-border/70 bg-surface2/50 p-5"
            >
              <div className="space-y-1">
                <h2 className="text-sm font-semibold text-text">Diagnostics</h2>
                <p className="text-xs leading-5 text-text-muted">
                  Review the failing request and server location before trying
                  again.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {details?.method ? (
                  <div className={informationRowClassName}>
                    <span className="text-xs font-medium uppercase tracking-[0.12em] text-text-subtle">
                      Request method
                    </span>
                    <span className="text-sm text-text">{details.method}</span>
                  </div>
                ) : null}

                {details?.path ? (
                  <div className={informationRowClassName}>
                    <span className="text-xs font-medium uppercase tracking-[0.12em] text-text-subtle">
                      Request path
                    </span>
                    <code className="break-all text-sm text-text">
                      {details.path}
                    </code>
                  </div>
                ) : null}

                {details?.serverUrl ? (
                  <div className={informationRowClassName}>
                    <span className="text-xs font-medium uppercase tracking-[0.12em] text-text-subtle">
                      Configured server URL
                    </span>
                    <code className="break-all text-sm text-text">
                      {details.serverUrl}
                    </code>
                  </div>
                ) : null}

                {details?.status !== undefined ? (
                  <div className={informationRowClassName}>
                    <span className="text-xs font-medium uppercase tracking-[0.12em] text-text-subtle">
                      Status
                    </span>
                    <span className="text-sm text-text">{details.status}</span>
                  </div>
                ) : null}
              </div>

              {details?.rawMessage ? (
                <div className="space-y-1">
                  <span className="text-xs font-medium uppercase tracking-[0.12em] text-text-subtle">
                    Raw message
                  </span>
                  <p className="rounded-2xl border border-border/70 bg-bg px-4 py-3 text-sm leading-6 text-text-muted">
                    {details.rawMessage}
                  </p>
                </div>
              ) : null}

              {details?.diagnostics ? (
                <div className="space-y-1">
                  <span className="text-xs font-medium uppercase tracking-[0.12em] text-text-subtle">
                    Additional diagnostics
                  </span>
                  <div className="rounded-2xl border border-border/70 bg-bg px-4 py-3 text-sm leading-6 text-text-muted">
                    <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-text-muted">
                      {formatStructuredValue(details.diagnostics)}
                    </pre>
                  </div>
                </div>
              ) : null}

              {details?.recentRequestError ? (
                <div className="space-y-1">
                  <span className="text-xs font-medium uppercase tracking-[0.12em] text-text-subtle">
                    Recent request error
                  </span>
                  <div className="rounded-2xl border border-border/70 bg-bg px-4 py-3 text-sm leading-6 text-text-muted">
                    <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-text-muted">
                      {formatStructuredValue(details.recentRequestError)}
                    </pre>
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="button"
              onClick={onRetry}
              className={`${actionButtonClassName} ${primaryActionClassName}`}
            >
              Try again
            </button>
            <button
              type="button"
              onClick={onReload}
              className={`${actionButtonClassName} ${secondaryActionClassName}`}
            >
              Reload page
            </button>
            <button
              type="button"
              onClick={onOpenDiagnostics}
              className={`${actionButtonClassName} ${secondaryActionClassName}`}
            >
              Open Health & diagnostics
            </button>
            <button
              type="button"
              onClick={onOpenSettings}
              className={`${actionButtonClassName} ${secondaryActionClassName}`}
            >
              Open Settings
            </button>
          </div>
        </div>
      </section>
    </main>
  )
}

export default BackendUnavailableRecovery
