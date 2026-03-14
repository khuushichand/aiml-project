import React from "react"

import { McpToolPicker } from "./McpToolPicker"
import { PERSONA_STARTER_COMMAND_TEMPLATES } from "./personaStarterCommandTemplates"

type SetupStarterCommandsStepProps = {
  saving: boolean
  onCreateFromTemplate: (templateKey: string) => void
  onCreateMcpStarter: (toolName: string, phrase: string) => void
  onSkip: () => void
}

export const SetupStarterCommandsStep: React.FC<SetupStarterCommandsStepProps> = ({
  saving,
  onCreateFromTemplate,
  onCreateMcpStarter,
  onSkip
}) => {
  const [toolName, setToolName] = React.useState("")
  const [phrase, setPhrase] = React.useState("")

  const handleCreateMcpStarter = React.useCallback(() => {
    const normalizedToolName = String(toolName || "").trim()
    const normalizedPhrase = String(phrase || "").trim()
    if (!normalizedToolName || !normalizedPhrase) return
    onCreateMcpStarter(normalizedToolName, normalizedPhrase)
  }, [onCreateMcpStarter, phrase, toolName])

  return (
    <div className="space-y-3">
      <div>
        <div className="text-sm font-semibold text-text">Starter commands</div>
        <div className="text-xs text-text-muted">
          Add a useful command now or continue explicitly without one.
        </div>
      </div>
      <div className="space-y-2">
        {PERSONA_STARTER_COMMAND_TEMPLATES.map((template) => (
          <button
            key={template.key}
            type="button"
            aria-label={template.label}
            className="flex w-full items-start justify-between rounded-lg border border-border bg-surface2 px-3 py-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
            disabled={saving}
            onClick={() => onCreateFromTemplate(template.key)}
          >
            <div>
              <div className="text-sm font-medium text-text">{template.label}</div>
              <div className="mt-1 text-xs text-text-muted">{template.description}</div>
            </div>
          </button>
        ))}
      </div>
      <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
        <div className="text-sm font-medium text-text">Add MCP starter</div>
        <McpToolPicker value={toolName} onChange={setToolName} disabled={saving} />
        <input
          type="text"
          value={phrase}
          aria-label="MCP starter phrase"
          placeholder="Phrase users can say"
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
          disabled={saving}
          onChange={(event) => setPhrase(event.target.value)}
        />
        <button
          type="button"
          className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
          disabled={saving || !String(toolName || "").trim() || !String(phrase || "").trim()}
          onClick={handleCreateMcpStarter}
        >
          Add MCP starter
        </button>
      </div>
      <button
        type="button"
        className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
        disabled={saving}
        onClick={onSkip}
      >
        Continue without starter commands
      </button>
    </div>
  )
}
