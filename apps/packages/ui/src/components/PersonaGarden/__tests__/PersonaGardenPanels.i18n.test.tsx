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
    fetchWithAuth: () =>
      Promise.resolve({
        ok: true,
        json: async () => ({ commands: [] })
      }),
    listPersonaExemplars: () => Promise.resolve([]),
    createPersonaExemplar: () => Promise.resolve({}),
    updatePersonaExemplar: () => Promise.resolve({}),
    importPersonaExemplars: () => Promise.resolve([]),
    reviewPersonaExemplar: () => Promise.resolve({})
  }
}))

vi.mock("@/hooks/useResolvedPersonaVoiceDefaults", () => ({
  PERSONA_TURN_DETECTION_BALANCED_DEFAULTS: {
    autoCommitEnabled: true,
    vadThreshold: 0.5,
    minSilenceMs: 250,
    turnStopSecs: 0.2,
    minUtteranceSecs: 0.4
  },
  useResolvedPersonaVoiceDefaults: () => ({
    sttLanguage: "en-US",
    sttModel: "whisper-1",
    ttsProvider: "tldw",
    ttsVoice: "af_heart",
    confirmationMode: "destructive_only",
    voiceChatTriggerPhrases: [],
    autoResume: true,
    bargeIn: false,
    autoCommitEnabled: true,
    vadThreshold: 0.5,
    minSilenceMs: 250,
    turnStopSecs: 0.2,
    minUtteranceSecs: 0.4
  })
}))

import { CommandsPanel } from "../CommandsPanel"
import { ConnectionsPanel } from "../ConnectionsPanel"
import { PersonaGardenTabs } from "../PersonaGardenTabs"
import { PoliciesPanel } from "../PoliciesPanel"
import { ProfilePanel } from "../ProfilePanel"
import { ScopesPanel } from "../ScopesPanel"
import { TestLabPanel } from "../TestLabPanel"
import { VoiceExamplesPanel } from "../VoiceExamplesPanel"

describe("Persona Garden panel i18n", () => {
  it("routes panel headings and helper copy through react-i18next", () => {
    render(
      <>
        <ProfilePanel
          selectedPersonaId="persona-1"
          selectedPersonaName="Persona One"
          personaCount={3}
          connected={false}
          sessionId={null}
          isActive={false}
        />
        <CommandsPanel
          selectedPersonaId=""
          selectedPersonaName=""
          isActive={false}
        />
        <TestLabPanel
          selectedPersonaId=""
          selectedPersonaName=""
          isActive={false}
        />
        <VoiceExamplesPanel
          selectedPersonaId=""
          selectedPersonaName=""
          isActive={false}
        />
        <ConnectionsPanel
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
      screen.queryByText("sidepanel:personaGarden.profile.noneSelected")
    ).not.toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.profile.assistantDefaultsHeading")
    ).toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.commands.heading")
    ).toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.testLab.heading")
    ).toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.voiceExamples.heading")
    ).toBeInTheDocument()
    expect(
      screen.getByText("sidepanel:personaGarden.connections.heading")
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
