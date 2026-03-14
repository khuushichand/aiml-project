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

  it("renders injected voice-step content when the wizard advances past persona choice", () => {
    render(
      <AssistantSetupWizard
        catalog={[{ id: "default_persona", name: "Default Persona" }]}
        selectedPersonaId="default_persona"
        currentStep="voice"
        postSetupTargetTab="profiles"
        voiceStepContent={<div data-testid="setup-voice-content">Voice step</div>}
        saving={false}
        error={null}
        onUsePersona={vi.fn()}
        onCreatePersona={vi.fn()}
      />
    )

    expect(screen.getByTestId("setup-voice-content")).toHaveTextContent("Voice step")
    expect(screen.queryByText("Setup step")).not.toBeInTheDocument()
  })

  it("renders injected commands-step content when the wizard reaches starter commands", () => {
    render(
      <AssistantSetupWizard
        catalog={[{ id: "default_persona", name: "Default Persona" }]}
        selectedPersonaId="default_persona"
        currentStep="commands"
        postSetupTargetTab="profiles"
        commandsStepContent={<div data-testid="setup-commands-content">Commands step</div>}
        saving={false}
        error={null}
        onUsePersona={vi.fn()}
        onCreatePersona={vi.fn()}
      />
    )

    expect(screen.getByTestId("setup-commands-content")).toHaveTextContent("Commands step")
    expect(screen.queryByText("Setup step")).not.toBeInTheDocument()
  })

  it("renders injected safety-step content when the wizard reaches safety and connections", () => {
    render(
      <AssistantSetupWizard
        catalog={[{ id: "default_persona", name: "Default Persona" }]}
        selectedPersonaId="default_persona"
        currentStep="safety"
        postSetupTargetTab="profiles"
        safetyStepContent={<div data-testid="setup-safety-content">Safety step</div>}
        saving={false}
        error={null}
        onUsePersona={vi.fn()}
        onCreatePersona={vi.fn()}
      />
    )

    expect(screen.getByTestId("setup-safety-content")).toHaveTextContent("Safety step")
    expect(screen.queryByText("Setup step")).not.toBeInTheDocument()
  })

  it("renders injected test-step content when the wizard reaches finish setup", () => {
    render(
      <AssistantSetupWizard
        catalog={[{ id: "default_persona", name: "Default Persona" }]}
        selectedPersonaId="default_persona"
        currentStep="test"
        postSetupTargetTab="profiles"
        testStepContent={<div data-testid="setup-test-content">Test step</div>}
        saving={false}
        error={null}
        onUsePersona={vi.fn()}
        onCreatePersona={vi.fn()}
      />
    )

    expect(screen.getByTestId("setup-test-content")).toHaveTextContent("Test step")
    expect(screen.queryByText("Setup step")).not.toBeInTheDocument()
  })
})
