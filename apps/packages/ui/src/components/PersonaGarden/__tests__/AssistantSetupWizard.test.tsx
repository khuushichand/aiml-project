import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AssistantSetupWizard } from "../AssistantSetupWizard"

describe("AssistantSetupWizard", () => {
  it("renders the persona-choice step first", () => {
    render(
      <AssistantSetupWizard
        catalog={[
          { id: "default_persona", name: "Default Persona" },
          { id: "helper", name: "Helper" }
        ]}
        selectedPersonaId="default_persona"
        currentStep="persona"
        postSetupTargetTab="profiles"
        saving={false}
        error={null}
        onUsePersona={vi.fn()}
        onCreatePersona={vi.fn()}
      />
    )

    expect(screen.getByTestId("assistant-setup-overlay")).toBeInTheDocument()
    expect(screen.getByText("Choose a persona")).toBeInTheDocument()
    expect(screen.getByText("Default Persona")).toBeInTheDocument()
    expect(screen.getByText("Helper")).toBeInTheDocument()
  })

  it("does not auto-select the existing default persona without an explicit click", () => {
    const onUsePersona = vi.fn()

    render(
      <AssistantSetupWizard
        catalog={[{ id: "default_persona", name: "Default Persona" }]}
        selectedPersonaId="default_persona"
        currentStep="persona"
        postSetupTargetTab="profiles"
        saving={false}
        error={null}
        onUsePersona={onUsePersona}
        onCreatePersona={vi.fn()}
      />
    )

    expect(onUsePersona).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Use this persona" }))

    expect(onUsePersona).toHaveBeenCalledWith("default_persona")
  })

  it("allows creating a new persona from the setup flow", () => {
    const onCreatePersona = vi.fn()

    render(
      <AssistantSetupWizard
        catalog={[{ id: "default_persona", name: "Default Persona" }]}
        selectedPersonaId="default_persona"
        currentStep="persona"
        postSetupTargetTab="profiles"
        saving={false}
        error={null}
        onUsePersona={vi.fn()}
        onCreatePersona={onCreatePersona}
      />
    )

    fireEvent.change(screen.getByPlaceholderText("New persona name"), {
      target: { value: "Garden Butler" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Create new persona" }))

    expect(onCreatePersona).toHaveBeenCalledWith("Garden Butler")
  })

  it("renders a non-persona step placeholder without persona-choice actions", () => {
    render(
      <AssistantSetupWizard
        catalog={[{ id: "default_persona", name: "Default Persona" }]}
        selectedPersonaId="default_persona"
        currentStep="voice"
        postSetupTargetTab="profiles"
        saving={false}
        error={null}
        onUsePersona={vi.fn()}
        onCreatePersona={vi.fn()}
      />
    )

    expect(screen.getByTestId("assistant-setup-current-step")).toHaveTextContent("voice")
    expect(screen.queryByRole("button", { name: "Use this persona" })).not.toBeInTheDocument()
  })
})
