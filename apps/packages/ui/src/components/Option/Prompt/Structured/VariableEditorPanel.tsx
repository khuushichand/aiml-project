import React from "react"
import { Plus, Trash2 } from "lucide-react"

type StructuredPromptVariable = {
  name: string
  required?: boolean
  input_type?: string
  label?: string
  description?: string
}

type VariableEditorPanelProps = {
  variables: StructuredPromptVariable[]
  previewValues: Record<string, string>
  onVariablesChange: (variables: StructuredPromptVariable[]) => void
  onPreviewValuesChange: (values: Record<string, string>) => void
}

export const VariableEditorPanel: React.FC<VariableEditorPanelProps> = ({
  variables,
  previewValues,
  onVariablesChange,
  onPreviewValuesChange
}) => {
  const updateVariable = (
    index: number,
    updates: Partial<StructuredPromptVariable>
  ) => {
    const next = variables.map((variable, currentIndex) =>
      currentIndex === index ? { ...variable, ...updates } : variable
    )
    onVariablesChange(next)
  }

  const removeVariable = (index: number) => {
    const next = variables.filter((_, currentIndex) => currentIndex !== index)
    onVariablesChange(next)
    const nextPreviewValues = { ...previewValues }
    const removedName = variables[index]?.name
    if (removedName) {
      delete nextPreviewValues[removedName]
      onPreviewValuesChange(nextPreviewValues)
    }
  }

  const addVariable = () => {
    onVariablesChange([
      ...variables,
      {
        name: `variable_${variables.length + 1}`,
        required: false,
        input_type: "text"
      }
    ])
  }

  return (
    <section className="rounded-xl border border-border bg-surface1 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-text">Variables</h3>
          <p className="text-xs text-text-muted">
            Define reusable prompt inputs and optional preview values.
          </p>
        </div>
        <button
          type="button"
          onClick={addVariable}
          data-testid="structured-variable-add"
          className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-text hover:bg-surface2"
        >
          <Plus className="size-3" />
          Add variable
        </button>
      </div>

      <div className="space-y-3">
        {variables.length === 0 && (
          <p className="text-sm text-text-muted">
            No variables yet. Add one to support dynamic prompt assembly.
          </p>
        )}

        {variables.map((variable, index) => (
          <div
            key={`${variable.name}-${index}`}
            className="rounded-lg border border-border bg-background p-3"
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
                Variable {index + 1}
              </span>
              <button
                type="button"
                onClick={() => removeVariable(index)}
                className="rounded border border-border p-1 text-danger hover:bg-danger/5"
              >
                <Trash2 className="size-3" />
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted">
                  Name
                </span>
                <input
                  type="text"
                  value={variable.name}
                  onChange={(event) =>
                    updateVariable(index, { name: event.target.value })
                  }
                  data-testid={`structured-variable-name-${index}`}
                  className="w-full rounded-md border border-border bg-surface1 px-3 py-2 text-sm text-text"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted">
                  Input type
                </span>
                <select
                  value={variable.input_type || "text"}
                  onChange={(event) =>
                    updateVariable(index, { input_type: event.target.value })
                  }
                  className="w-full rounded-md border border-border bg-surface1 px-3 py-2 text-sm text-text"
                >
                  <option value="text">Text</option>
                  <option value="textarea">Textarea</option>
                  <option value="number">Number</option>
                  <option value="boolean">Boolean</option>
                  <option value="select">Select</option>
                  <option value="json">JSON</option>
                </select>
              </label>
            </div>

            <label className="mt-3 flex items-center gap-2 text-sm text-text">
              <input
                type="checkbox"
                checked={!!variable.required}
                onChange={(event) =>
                  updateVariable(index, { required: event.target.checked })
                }
              />
              Required
            </label>
          </div>
        ))}
      </div>

      {variables.length > 0 && (
        <div className="mt-4 space-y-3 border-t border-border pt-4">
          <div>
            <h4 className="text-sm font-semibold text-text">Preview inputs</h4>
            <p className="text-xs text-text-muted">
              Sample values passed to the backend preview endpoint.
            </p>
          </div>
          {variables.map((variable) => (
            <label key={`preview-${variable.name}`} className="block">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted">
                {variable.name}
              </span>
              <input
                type="text"
                value={previewValues[variable.name] || ""}
                onChange={(event) =>
                  onPreviewValuesChange({
                    ...previewValues,
                    [variable.name]: event.target.value
                  })
                }
                data-testid={`structured-preview-variable-${variable.name}`}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text"
              />
            </label>
          ))}
        </div>
      )}
    </section>
  )
}
