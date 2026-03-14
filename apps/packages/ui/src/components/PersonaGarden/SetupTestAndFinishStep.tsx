import React from "react"

type SetupDryRunResult = {
  heardText: string
  matched: boolean
  commandName?: string | null
  failurePhase?: string | null
}

type SetupTestAndFinishStepProps = {
  saving: boolean
  dryRunLoading: boolean
  dryRunError: string | null
  dryRunResult: SetupDryRunResult | null
  liveConnected: boolean
  liveSuccessText: string | null
  onRunDryRun: (heardText: string) => void
  onConnectLive: () => void
  onSendLive: (text: string) => void
  onFinishWithDryRun: () => void
  onFinishWithLiveSession: () => void
}

export const SetupTestAndFinishStep: React.FC<SetupTestAndFinishStepProps> = ({
  saving,
  dryRunLoading,
  dryRunError,
  dryRunResult,
  liveConnected,
  liveSuccessText,
  onRunDryRun,
  onConnectLive,
  onSendLive,
  onFinishWithDryRun,
  onFinishWithLiveSession
}) => {
  const [dryRunHeardText, setDryRunHeardText] = React.useState("")
  const [liveText, setLiveText] = React.useState("")

  return (
    <div className="space-y-4">
      <div>
        <div className="text-sm font-semibold text-text">Test and finish</div>
        <div className="text-xs text-text-muted">
          Run one successful test before using this assistant normally. You can
          finish with a dry-run or from a live session response.
        </div>
      </div>

      <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
        <div className="text-sm font-medium text-text">Dry-run test</div>
        <textarea
          value={dryRunHeardText}
          placeholder="Try a spoken phrase"
          className="min-h-[88px] w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
          onChange={(event) => setDryRunHeardText(event.target.value)}
        />
        {dryRunError ? (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
            {dryRunError}
          </div>
        ) : null}
        {dryRunResult ? (
          <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
            {dryRunResult.matched
              ? `Matched ${dryRunResult.commandName || "a command"} for "${dryRunResult.heardText}".`
              : `Dry-run completed for "${dryRunResult.heardText}".`}
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
          {dryRunResult ? (
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
          <button
            type="button"
            className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
            disabled={saving}
            onClick={onConnectLive}
          >
            Connect live session
          </button>
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
          </>
        )}
        {liveSuccessText ? (
          <div className="rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
            Live session responded: {liveSuccessText}
          </div>
        ) : null}
        {liveSuccessText ? (
          <button
            type="button"
            className="rounded-md border border-sky-500/40 px-3 py-2 text-sm font-medium text-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={saving}
            onClick={onFinishWithLiveSession}
          >
            Finish with live session
          </button>
        ) : null}
      </div>
    </div>
  )
}
