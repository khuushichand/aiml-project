import React from "react"

export const BlocklistSyntaxRef: React.FC = () => {
  const [open, setOpen] = React.useState(false)

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-text-muted hover:text-text hover:bg-surface/50 transition-colors"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span>Blocklist Syntax Reference</span>
        <span className={`transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-border">
          <table className="w-full text-sm mt-3">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="pb-2 pr-4 font-medium">Syntax</th>
                <th className="pb-2 font-medium">Example</th>
              </tr>
            </thead>
            <tbody className="font-mono text-xs">
              <tr><td className="py-1 pr-4 text-text-muted">Literal</td><td><code>badword</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Regex</td><td><code>{"/\\bnsfw\\b/"}</code> or <code>{"/pattern/imsx"}</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Action</td><td><code>{"pattern -> block|redact|warn"}</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Redact sub</td><td><code>{"/pat/ -> redact:[MASK]"}</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Categories</td><td><code>{"/pat/ -> block #pii,confidential"}</code></td></tr>
              <tr><td className="py-1 pr-4 text-text-muted">Comment</td><td><code>{"# This is a comment"}</code></td></tr>
            </tbody>
          </table>
          <p className="mt-3 text-xs text-text-muted">
            Nested quantifiers and patterns {">"} 2000 chars are rejected to prevent ReDoS.
            Case-insensitive matching by default.
          </p>
        </div>
      )}
    </div>
  )
}
