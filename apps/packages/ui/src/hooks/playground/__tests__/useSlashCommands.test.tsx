// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { useSlashCommands } from "../useSlashCommands"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallback?: string,
      values?: Record<string, unknown>
    ) => {
      const base = fallback || key
      if (!values) return base
      return Object.entries(values).reduce((acc, [name, value]) => {
        return acc.replaceAll(`{{${name}}}`, String(value))
      }, base)
    }
  })
}))

describe("playground useSlashCommands", () => {
  it("shows slash suggestions with concise descriptions and examples", () => {
    const { result } = renderHook(() =>
      useSlashCommands({
        chatMode: "normal",
        setChatMode: vi.fn(),
        webSearch: false,
        setWebSearch: vi.fn(),
        handleImageUpload: vi.fn(),
        imageBackendDefaultTrimmed: "",
        imageBackendLabel: "none",
        setOpenModelSettings: vi.fn(),
        currentMessage: "/gen"
      })
    )

    expect(result.current.showSlashMenu).toBe(true)
    const generateImage = result.current.filteredSlashCommands.find(
      (command) => command.command === "generate-image"
    )
    expect(generateImage).toBeDefined()
    expect(generateImage?.description).toContain("/generate-image:<provider>")
  })

  it("applies slash command actions when submission intent is resolved", () => {
    const setChatMode = vi.fn()
    const setWebSearch = vi.fn()
    const { result } = renderHook(() =>
      useSlashCommands({
        chatMode: "normal",
        setChatMode,
        webSearch: false,
        setWebSearch,
        handleImageUpload: vi.fn(),
        imageBackendDefaultTrimmed: "flux",
        imageBackendLabel: "Flux",
        setOpenModelSettings: vi.fn(),
        currentMessage: "/web"
      })
    )

    let intent:
      | ReturnType<typeof result.current.resolveSubmissionIntent>
      | undefined
    act(() => {
      intent = result.current.resolveSubmissionIntent("/web")
    })

    expect(intent).toMatchObject({
      handled: true,
      isImageCommand: false,
      message: ""
    })
    expect(setWebSearch).toHaveBeenCalledWith(true)

    const imageIntent = result.current.resolveSubmissionIntent(
      "/generate-image:flux city skyline"
    )
    expect(imageIntent).toMatchObject({
      handled: true,
      isImageCommand: true,
      imageBackendOverride: "flux",
      message: "city skyline"
    })
  })
})
