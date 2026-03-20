// @vitest-environment jsdom

import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AdminAudioInstallerCard } from "../AdminAudioInstallerCard"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string },
      maybeOptions?: { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return fallbackOrOptions
      }
      if (
        fallbackOrOptions &&
        typeof fallbackOrOptions === "object" &&
        typeof fallbackOrOptions.defaultValue === "string"
      ) {
        return fallbackOrOptions.defaultValue
      }
      return maybeOptions?.defaultValue || key
    }
  })
}))

vi.mock("@/components/Option/Setup/AudioInstallerPanel", () => ({
  AudioInstallerPanel: () => <div data-testid="audio-installer-panel">Audio Installer Panel</div>
}))

describe("AdminAudioInstallerCard", () => {
  it("renders the shared audio installer with server-scoped framing", () => {
    render(<AdminAudioInstallerCard />)

    expect(screen.getByText("Audio installer")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Install and verify server-side STT/TTS bundles for this connected server."
      )
    ).toBeInTheDocument()
    expect(screen.getByTestId("audio-installer-panel")).toBeInTheDocument()
  })
})
