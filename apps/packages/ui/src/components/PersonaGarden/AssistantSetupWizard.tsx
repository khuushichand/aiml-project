import React from "react"

import type { PersonaSetupStep } from "@/hooks/usePersonaSetupWizard"
import type { PersonaGardenTabKey } from "@/utils/persona-garden-route"

type AssistantSetupWizardProps = {
  catalog: Array<{ id: string; name: string }>
  selectedPersonaId: string
  currentStep: PersonaSetupStep
  postSetupTargetTab: PersonaGardenTabKey
  voiceStepContent?: React.ReactNode
  commandsStepContent?: React.ReactNode
  safetyStepContent?: React.ReactNode
  testStepContent?: React.ReactNode
  saving: boolean
  error: string | null
  onUsePersona: (personaId: string) => void
  onCreatePersona: (name: string) => void
}

export const AssistantSetupWizard: React.FC<AssistantSetupWizardProps> = ({
  catalog,
  selectedPersonaId,
  currentStep,
  postSetupTargetTab,
  voiceStepContent,
  commandsStepContent,
  safetyStepContent,
  testStepContent,
  saving,
  error,
  onUsePersona,
  onCreatePersona
}) => {
  const [newPersonaName, setNewPersonaName] = React.useState("")

  const handleCreatePersona = React.useCallback(() => {
    const normalizedName = String(newPersonaName || "").trim()
    if (!normalizedName) return
    onCreatePersona(normalizedName)
  }, [newPersonaName, onCreatePersona])

  return (
    <div
      data-testid="assistant-setup-overlay"
      className="flex flex-1 flex-col gap-3 rounded-xl border border-border bg-surface p-4"
    >
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
          Assistant Setup
        </div>
        <div className="mt-2 text-sm text-text">
          Finish setup before using this persona in Persona Garden.
        </div>
      </div>
      <div
        data-testid="assistant-setup-current-step"
        className="text-sm font-medium text-text"
      >
        {currentStep}
      </div>
      <div
        data-testid="assistant-setup-post-target"
        className="text-xs text-text-muted"
      >
        {postSetupTargetTab}
      </div>
      {error ? (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      ) : null}
      {currentStep === "persona" ? (
        <div className="space-y-3">
          <div>
            <div className="text-sm font-semibold text-text">Choose a persona</div>
            <div className="text-xs text-text-muted">
              Pick an existing persona or create a new one before continuing.
            </div>
          </div>
          <div className="space-y-2">
            {catalog.map((persona) => {
              const isSelected =
                String(persona.id || "").trim() === String(selectedPersonaId || "").trim()
              return (
                <div
                  key={persona.id}
                  className="flex items-center justify-between rounded-lg border border-border bg-surface2 px-3 py-2"
                >
                  <div>
                    <div className="text-sm font-medium text-text">{persona.name}</div>
                    <div className="text-xs text-text-muted">{persona.id}</div>
                  </div>
                  <button
                    type="button"
                    className="rounded-md border border-border px-3 py-1 text-xs font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={saving}
                    data-selected={isSelected ? "true" : "false"}
                    onClick={() => onUsePersona(persona.id)}
                  >
                    Use this persona
                  </button>
                </div>
              )
            })}
          </div>
          <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
            <div className="text-sm font-medium text-text">Create new persona</div>
            <input
              type="text"
              value={newPersonaName}
              placeholder="New persona name"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
              onChange={(event) => setNewPersonaName(event.target.value)}
            />
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
              disabled={saving || !String(newPersonaName || "").trim()}
              onClick={handleCreatePersona}
            >
              Create new persona
            </button>
          </div>
        </div>
      ) : currentStep === "voice" && voiceStepContent ? (
        voiceStepContent
      ) : currentStep === "commands" && commandsStepContent ? (
        commandsStepContent
      ) : currentStep === "safety" && safetyStepContent ? (
        safetyStepContent
      ) : currentStep === "test" && testStepContent ? (
        testStepContent
      ) : (
        <div className="rounded-lg border border-border bg-surface2 p-3 text-sm text-text">
          Setup step <span className="font-medium">{currentStep}</span> will continue here.
        </div>
      )}
    </div>
  )
}
