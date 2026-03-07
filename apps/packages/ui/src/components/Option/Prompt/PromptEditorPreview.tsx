import React, { useMemo, useState } from "react"
import {
  extractTemplateVariables,
  tokenizeTemplateVariableHighlights,
} from "./prompt-template-variable-utils"
import {
  estimatePromptTokens,
  getPromptTokenBudgetState,
} from "./prompt-length-utils"

type Props = {
  systemPrompt: string
  userPrompt: string
}

export const PromptEditorPreview: React.FC<Props> = ({
  systemPrompt,
  userPrompt,
}) => {
  const [varValues, setVarValues] = useState<Record<string, string>>({})

  const variables = useMemo(() => {
    const allText = `${systemPrompt} ${userPrompt}`
    return extractTemplateVariables(allText)
  }, [systemPrompt, userPrompt])

  const renderHighlighted = (text: string) => {
    if (!text) return <span className="text-text-muted italic">Empty</span>
    const tokens = tokenizeTemplateVariableHighlights(text)
    return tokens.map((token, i) => {
      if (token.isVariable) {
        const val = varValues[token.variableName || ""]
        if (val) {
          return (
            <span key={i} className="rounded bg-green-500/20 px-0.5">
              {val}
            </span>
          )
        }
        return (
          <span key={i} className="rounded bg-primary/20 px-0.5 text-primary">
            {token.text}
          </span>
        )
      }
      return <span key={i}>{token.text}</span>
    })
  }

  const sysTokens = estimatePromptTokens(systemPrompt)
  const userTokens = estimatePromptTokens(userPrompt)
  const totalTokens = sysTokens + userTokens
  const budgetState = getPromptTokenBudgetState(totalTokens)

  const tokenColor =
    budgetState === "danger"
      ? "text-danger"
      : budgetState === "warning"
      ? "text-warning"
      : "text-text-muted"

  return (
    <div
      className="flex h-full flex-col overflow-y-auto"
      data-testid="prompt-editor-preview"
    >
      {/* Rendered preview */}
      <div className="flex-1 space-y-4 p-4">
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-text-muted">
            System Prompt
          </h4>
          <div className="whitespace-pre-wrap rounded border border-border bg-surface p-3 text-sm leading-relaxed">
            {renderHighlighted(systemPrompt)}
          </div>
        </div>

        {userPrompt && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-text-muted">
              User Message
            </h4>
            <div className="whitespace-pre-wrap rounded border border-border bg-surface p-3 text-sm leading-relaxed">
              {renderHighlighted(userPrompt)}
            </div>
          </div>
        )}

        {/* Template variables */}
        {variables.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
              Template Variables
            </h4>
            <div className="space-y-2">
              {variables.map((v) => (
                <div key={v} className="flex items-center gap-2">
                  <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono text-primary">
                    {`{{${v}}}`}
                  </span>
                  <input
                    type="text"
                    value={varValues[v] || ""}
                    onChange={(e) =>
                      setVarValues((prev) => ({
                        ...prev,
                        [v]: e.target.value,
                      }))
                    }
                    placeholder={`Enter ${v}...`}
                    className="flex-1 rounded border border-border bg-surface px-2 py-1 text-sm outline-none focus:border-primary"
                    data-testid={`preview-var-${v}`}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Token count footer */}
      <div className="border-t border-border px-4 py-2">
        <div className={`flex items-center gap-3 text-xs ${tokenColor}`}>
          <span>System: ~{sysTokens} tokens</span>
          <span>User: ~{userTokens} tokens</span>
          <span className="font-medium">Total: ~{totalTokens} tokens</span>
        </div>
      </div>
    </div>
  )
}
