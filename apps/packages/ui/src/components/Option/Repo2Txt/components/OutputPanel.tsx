type OutputPanelProps = {
  output: string
  busy: boolean
  canGenerate: boolean
  onGenerate: () => void | Promise<void>
  onCopy: () => void | Promise<void>
  onDownload: () => void
}

export function OutputPanel({
  output,
  busy,
  canGenerate,
  onGenerate,
  onCopy,
  onDownload
}: OutputPanelProps) {
  return (
    <section className="space-y-3">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold">Output</h2>
        <button
          type="button"
          className="rounded border px-3 py-1.5 text-sm"
          onClick={() => void onGenerate()}
          disabled={!canGenerate || busy}
        >
          Generate Output
        </button>
        <button
          type="button"
          className="rounded border px-3 py-1.5 text-sm"
          onClick={() => void onCopy()}
          disabled={output.trim().length === 0}
        >
          Copy
        </button>
        <button
          type="button"
          className="rounded border px-3 py-1.5 text-sm"
          onClick={onDownload}
          disabled={output.trim().length === 0}
        >
          Download
        </button>
      </header>
      <textarea
        value={output}
        readOnly
        rows={14}
        className="w-full rounded border p-3 text-xs"
        aria-label="Repo2txt output preview"
      />
    </section>
  )
}
