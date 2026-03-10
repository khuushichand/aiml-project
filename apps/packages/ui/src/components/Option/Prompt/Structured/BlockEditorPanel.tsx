import React from "react"

type StructuredPromptBlock = {
  id: string
  name: string
  role: "system" | "developer" | "user" | "assistant"
  content: string
  enabled: boolean
  order: number
  is_template: boolean
}

type BlockEditorPanelProps = {
  block: StructuredPromptBlock | null
  onChange: (updates: Partial<StructuredPromptBlock>) => void
}

export const BlockEditorPanel: React.FC<BlockEditorPanelProps> = ({
  block,
  onChange
}) => {
  if (!block) {
    return (
      <section className="rounded-xl border border-border bg-surface1 p-4">
        <h3 className="text-sm font-semibold text-text">Block editor</h3>
        <p className="mt-2 text-sm text-text-muted">
          Select a block to edit its role, content, and template behavior.
        </p>
      </section>
    )
  }

  return (
    <section className="rounded-xl border border-border bg-surface1 p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-text">Block editor</h3>
        <p className="text-xs text-text-muted">
          Keep each block focused on one job: identity, task, constraints, or examples.
        </p>
      </div>

      <div className="space-y-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted">
            Name
          </span>
          <input
            type="text"
            value={block.name}
            onChange={(event) => onChange({ name: event.target.value })}
            data-testid="structured-block-name"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted">
            Role
          </span>
          <select
            value={block.role}
            onChange={(event) =>
              onChange({
                role: event.target.value as StructuredPromptBlock["role"]
              })
            }
            data-testid="structured-block-role"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text"
          >
            <option value="system">System</option>
            <option value="developer">Developer</option>
            <option value="user">User</option>
            <option value="assistant">Assistant</option>
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted">
            Content
          </span>
          <textarea
            value={block.content}
            onChange={(event) => onChange({ content: event.target.value })}
            rows={8}
            data-testid="structured-block-content"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text"
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={block.enabled}
              onChange={(event) => onChange({ enabled: event.target.checked })}
              data-testid="structured-block-enabled"
            />
            Enabled
          </label>
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={block.is_template}
              onChange={(event) =>
                onChange({ is_template: event.target.checked })
              }
              data-testid="structured-block-template"
            />
            Uses variables
          </label>
        </div>
      </div>
    </section>
  )
}
