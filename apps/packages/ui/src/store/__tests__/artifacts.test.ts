// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useArtifactsStore, type ArtifactItem } from "../artifacts"

const artifactFixture: ArtifactItem = {
  id: "artifact-1",
  title: "Example",
  content: "console.log('example')",
  kind: "code",
  language: "typescript"
}

const resetArtifactsStore = () => {
  useArtifactsStore.setState((state) => ({
    ...state,
    active: null,
    isOpen: false,
    isPinned: false,
    history: [],
    unreadCount: 0
  }))
}

describe("artifacts store responsive behavior", () => {
  const originalMatchMedia = window.matchMedia

  beforeEach(() => {
    resetArtifactsStore()
  })

  afterEach(() => {
    window.matchMedia = originalMatchMedia
    vi.restoreAllMocks()
    resetArtifactsStore()
  })

  it("opens panel immediately for manual artifact opens", () => {
    useArtifactsStore.getState().openArtifact(artifactFixture)
    const state = useArtifactsStore.getState()

    expect(state.isOpen).toBe(true)
    expect(state.unreadCount).toBe(0)
    expect(state.active?.id).toBe("artifact-1")
    expect(state.history).toHaveLength(1)
  })

  it("keeps panel closed and increments unread for auto opens on compact viewport", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === "(max-width: 1023px)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn()
    })) as any

    useArtifactsStore
      .getState()
      .openArtifact({ ...artifactFixture, id: "artifact-compact" }, { auto: true })

    const state = useArtifactsStore.getState()
    expect(state.isOpen).toBe(false)
    expect(state.unreadCount).toBe(1)
    expect(state.active?.id).toBe("artifact-compact")
    expect(state.history[0]?.id).toBe("artifact-compact")
  })

  it("marks unread artifacts read when reopening panel", () => {
    useArtifactsStore.setState((state) => ({
      ...state,
      active: artifactFixture,
      isOpen: false,
      unreadCount: 3,
      history: [artifactFixture]
    }))

    useArtifactsStore.getState().setOpen(true)
    const state = useArtifactsStore.getState()

    expect(state.isOpen).toBe(true)
    expect(state.unreadCount).toBe(0)
  })
})
