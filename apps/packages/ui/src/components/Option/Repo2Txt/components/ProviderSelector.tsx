import type { ChangeEvent } from "react"

type ProviderKind = "github" | "local" | null

type ProviderSelectorProps = {
  provider: ProviderKind
  githubUrl: string
  busy: boolean
  onSelectProvider: (provider: Exclude<ProviderKind, null>) => void
  onGithubUrlChange: (value: string) => void
  onLoadGithub: () => void | Promise<void>
  onLocalFilesSelected: (files: FileList) => void | Promise<void>
}

const handleFileSelection = (
  event: ChangeEvent<HTMLInputElement>,
  callback: (files: FileList) => void | Promise<void>
) => {
  const files = event.target.files
  if (!files || files.length === 0) return
  void callback(files)
}

export function ProviderSelector({
  provider,
  githubUrl,
  busy,
  onSelectProvider,
  onGithubUrlChange,
  onLoadGithub,
  onLocalFilesSelected
}: ProviderSelectorProps) {
  return (
    <section className="space-y-3">
      <header>
        <h2 className="text-sm font-semibold">Source Provider</h2>
      </header>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded border px-3 py-1.5 text-sm"
          aria-pressed={provider === "github"}
          onClick={() => onSelectProvider("github")}
        >
          GitHub
        </button>
        <button
          type="button"
          className="rounded border px-3 py-1.5 text-sm"
          aria-pressed={provider === "local"}
          onClick={() => onSelectProvider("local")}
        >
          Local
        </button>
      </div>

      {provider === "github" && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="url"
            value={githubUrl}
            onChange={(event) => onGithubUrlChange(event.target.value)}
            placeholder="https://github.com/owner/repo"
            className="min-w-[260px] flex-1 rounded border px-3 py-1.5 text-sm"
          />
          <button
            type="button"
            className="rounded border px-3 py-1.5 text-sm"
            onClick={() => void onLoadGithub()}
            disabled={busy || githubUrl.trim().length === 0}
          >
            Load Source
          </button>
        </div>
      )}

      {provider === "local" && (
        <div className="space-y-2">
          <label className="inline-flex cursor-pointer items-center gap-2 rounded border px-3 py-1.5 text-sm">
            <span>Choose Directory / Zip</span>
            <input
              type="file"
              className="hidden"
              onChange={(event) => handleFileSelection(event, onLocalFilesSelected)}
              multiple
            />
          </label>
        </div>
      )}
    </section>
  )
}
