import React from "react"

export type SetupTestOutcome =
  | {
      kind: "dry_run_match"
      heardText: string
      commandName?: string | null
    }
  | {
      kind: "dry_run_no_match"
      heardText: string
      failurePhase?: string | null
    }
  | {
      kind: "dry_run_failure"
      message: string
    }
  | {
      kind: "live_unavailable"
    }
  | {
      kind: "live_sent"
      text: string
    }
  | {
      kind: "live_success"
      text: string
      responseText: string
    }
  | {
      kind: "live_failure"
      text: string
      message: string
    }

type SetupTestAndFinishStepProps = {
  saving: boolean
  dryRunLoading: boolean
  liveConnected: boolean
  error?: string | null
  initialHeardText?: string | null
  notice?: string | null
  outcome: SetupTestOutcome | null
  onRunDryRun: (heardText: string) => void
  onCreateCommandFromPhrase?: (heardText: string) => void
  onConnectLive: () => void
  onSendLive: (text: string) => void
  onFinishWithDryRun: () => void
  onFinishWithLiveSession: () => void
}

export const SetupTestAndFinishStep: React.FC<SetupTestAndFinishStepProps> = ({
  saving,
  dryRunLoading,
  liveConnected,
  error = null,
  initialHeardText = null,
  notice = null,
  outcome,
  onRunDryRun,
  onCreateCommandFromPhrase,
  onConnectLive,
  onSendLive,
  onFinishWithDryRun,
  onFinishWithLiveSession
}) => {
  const [dryRunHeardText, setDryRunHeardText] = React.useState("")
  const [liveText, setLiveText] = React.useState("")

  React.useEffect(() => {
    const normalizedHeardText = String(initialHeardText || "").trim()
    if (!normalizedHeardText) return
    setDryRunHeardText(normalizedHeardText)
  }, [initialHeardText])

  const dryRunOutcome = React.useMemo(() => {
    if (!outcome || !outcome.kind.startsWith("dry_run_")) return null
    return outcome
  }, [outcome])

  const liveOutcome = React.useMemo(() => {
    if (!outcome || !outcome.kind.startsWith("live_")) return null
    return outcome
  }, [outcome])

  return (
    <div className="space-y-4">
      <div>
        <div className="text-sm font-semibold text-text">Test and finish</div>
        <div className="text-xs text-text-muted">
          Run one successful test before using this assistant normally. You can
          finish with a dry-run or from a live session response.
        </div>
      </div>
      {error ? (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
          {notice}
        </div>
      ) : null}

      <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
        <div className="text-sm font-medium text-text">Dry-run test</div>
        <textarea
          value={dryRunHeardText}
          placeholder="Try a spoken phrase"
          className="min-h-[88px] w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
          onChange={(event) => setDryRunHeardText(event.target.value)}
        />
        {dryRunOutcome?.kind === "dry_run_failure" ? (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
            <div>{dryRunOutcome.message}</div>
            <div className="mt-1 text-red-100/90">
              Retry the dry-run test or continue with a live session instead.
            </div>
          </div>
        ) : null}
        {dryRunOutcome?.kind === "dry_run_match" ? (
          <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
            Matched {dryRunOutcome.commandName || "a command"} for "{dryRunOutcome.heardText}".
          </div>
        ) : null}
        {dryRunOutcome?.kind === "dry_run_no_match" ? (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
            No direct command matched for "{dryRunOutcome.heardText}". You can
            continue by trying live voice or refining starter commands first.
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
            disabled={saving || dryRunLoading || !String(dryRunHeardText || "").trim()}
            onClick={() => onRunDryRun(String(dryRunHeardText || "").trim())}
          >
            {dryRunLoading ? "Running..." : "Run dry-run test"}
          </button>
          {dryRunOutcome?.kind === "dry_run_no_match" ? (
            <button
              type="button"
              className="rounded-md border border-amber-500/40 px-3 py-2 text-sm font-medium text-amber-200 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={saving}
              onClick={() => onCreateCommandFromPhrase?.(dryRunOutcome.heardText)}
            >
              Create command from this phrase
            </button>
          ) : null}
          {dryRunOutcome?.kind === "dry_run_match" ? (
            <button
              type="button"
              className="rounded-md border border-emerald-500/40 px-3 py-2 text-sm font-medium text-emerald-200 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={saving}
              onClick={onFinishWithDryRun}
            >
              Finish with dry-run test
            </button>
          ) : null}
        </div>
      </div>

      <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
        <div className="text-sm font-medium text-text">Live session test</div>
        {!liveConnected ? (
          <>
            {liveOutcome?.kind === "live_unavailable" ? (
              <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                Live session unavailable until you connect. Connect or reconnect the
                live session to keep going.
              </div>
            ) : null}
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
              disabled={saving}
              onClick={onConnectLive}
            >
              {liveOutcome?.kind === "live_unavailable"
                ? "Retry live connection"
                : "Connect live session"}
            </button>
          </>
        ) : (
          <>
            <textarea
              value={liveText}
              placeholder="Try a live message"
              className="min-h-[88px] w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
              onChange={(event) => setLiveText(event.target.value)}
            />
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
              disabled={saving || !String(liveText || "").trim()}
              onClick={() => onSendLive(String(liveText || "").trim())}
            >
              Send live test
            </button>
            {liveOutcome?.kind === "live_failure" ? (
              <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                <div>{liveOutcome.message}</div>
                <div className="mt-1 text-red-100/90">
                  Try sending the live test again or reconnect the live session.
                </div>
              </div>
            ) : null}
            {liveOutcome?.kind === "live_sent" ? (
              <div className="rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
                Live test sent: {liveOutcome.text}
              </div>
            ) : null}
            {liveOutcome?.kind === "live_success" ? (
              <div className="space-y-2">
                <div className="rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
                  Live session responded: {liveOutcome.responseText}
                </div>
                <button
                  type="button"
                  className="rounded-md border border-sky-500/40 px-3 py-2 text-sm font-medium text-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={saving}
                  onClick={onFinishWithLiveSession}
                >
                  Finish with live session
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}
