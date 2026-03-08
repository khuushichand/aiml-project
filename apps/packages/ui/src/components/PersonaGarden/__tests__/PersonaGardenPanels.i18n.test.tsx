import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    listPersonaExemplars: () => Promise.resolve([]),
    createPersonaExemplar: () => Promise.resolve({}),
    updatePersonaExemplar: () => Promise.resolve({})
  }
}))

import { PersonaGardenTabs } from "../PersonaGardenTabs"
import { PoliciesPanel } from "../PoliciesPanel"
import { ProfilePanel } from "../ProfilePanel"
import { ScopesPanel } from "../ScopesPanel"
import { VoiceExamplesPanel } from "../VoiceExamplesPanel"

describe("Persona Garden panel i18n", () => {
  it("routes panel headings and helper copy through react-i18next", () => {
    render(
      <>
        <ProfilePanel
          selectedPersonaId=""
          selectedPersonaName=""
          personaCount={3}
          connected={false}
          sessionId={null}
        />
        <VoiceExamplesPanel
          selectedPersonaId=""
          selectedPersonaName=""
          isActive={false}
        />
        <PoliciesPanel hasPendingPlan={false} />
        <ScopesPanel selectedPersonaName="" />
      </>
    )

    expect(
      screen.getByText("sidepanel:personaGarden.profile.heading")
    ).toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.profile.noneSelected")
    ).toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.voiceExamples.heading")
    ).toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.policies.heading")
    ).toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.scopes.heading")
    ).toBeInTheDocument()
  })

  it("routes the tablist aria label through react-i18next", () => {
    render(
      <PersonaGardenTabs
        activeKey="live"
        items={[
          {
            key: "live",
            label: "Live Session",
            content: <div>live panel</div>
          }
        ]}
        onChange={() => undefined}
      />
    )

    expect(screen.getByRole("tablist")).toHaveAttribute(
      "aria-label",
      "sidepanel:personaGarden.tabs.ariaLabel"
    )
  })
})
