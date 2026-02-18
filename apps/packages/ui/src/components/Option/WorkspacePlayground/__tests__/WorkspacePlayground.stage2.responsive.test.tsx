import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { WorkspacePlayground } from "../index"

const testState = {
  isMobile: false,
  storeHydrated: true,
  leftPaneCollapsed: false,
  rightPaneCollapsed: false,
  workspaceId: "workspace-1",
  initializeWorkspace: vi.fn(),
  addSources: vi.fn(),
  setSelectedSourceIds: vi.fn(),
  captureToCurrentNote: vi.fn(),
  selectedSourceIds: [] as string[],
  generatedArtifacts: [] as Array<{ id: string }>,
  setLeftPaneCollapsed: vi.fn(),
  setRightPaneCollapsed: vi.fn(),
  sources: [] as Array<{
    id: string
    mediaId: number
    title: string
    type: "pdf" | "video" | "audio" | "website" | "document" | "text"
    addedAt: Date
  }>,
  currentNote: {
    title: "",
    content: "",
    keywords: [] as string[],
    isDirty: false
  },
  workspaceChatSessions: {} as Record<string, { messages: any[] }>,
  focusSourceById: vi.fn(() => true),
  focusChatMessageById: vi.fn(() => true),
  focusWorkspaceNote: vi.fn(),
  setSourceStatusByMediaId: vi.fn()
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => testState.isMobile
}))

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: (
    selector: (state: typeof testState) => unknown
  ) => selector(testState)
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getMediaDetails: vi.fn().mockResolvedValue({})
  }
}))

vi.mock("@/utils/workspace-playground-prefill", () => ({
  consumeWorkspacePlaygroundPrefill: vi.fn().mockResolvedValue(null),
  buildKnowledgeQaSeedNote: vi.fn().mockReturnValue("")
}))

vi.mock("../WorkspaceHeader", () => ({
  WorkspaceHeader: () => <div data-testid="workspace-header" />
}))

vi.mock("../SourcesPane", () => ({
  SourcesPane: () => <div data-testid="workspace-sources-pane">Sources</div>
}))

vi.mock("../ChatPane", () => ({
  ChatPane: () => <div data-testid="workspace-chat-pane">Chat</div>
}))

vi.mock("../StudioPane", () => ({
  StudioPane: () => <div data-testid="workspace-studio-pane">Studio</div>
}))

vi.mock("antd", () => ({
  Drawer: ({ placement, mask, open, children }: any) => (
    <div
      data-testid={`workspace-drawer-${placement}`}
      data-mask={String(mask)}
      data-open={String(open)}
    >
      {children}
    </div>
  ),
  Tabs: ({ items }: any) => (
    <div>
      {Array.isArray(items)
        ? items.map((item: any) => (
            <div key={item.key} data-testid={`tab-${item.key}`}>
              {item.children}
            </div>
          ))
        : null}
    </div>
  ),
  Modal: ({ open, children, title }: any) =>
    open ? <div aria-label={String(title)}>{children}</div> : null,
  Input: (props: any) => <input {...props} />,
  Empty: ({ description }: any) => <div>{description}</div>
}))

describe("WorkspacePlayground Stage 2 drawer responsiveness", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testState.isMobile = false
    testState.storeHydrated = true
    testState.leftPaneCollapsed = false
    testState.rightPaneCollapsed = false
    testState.setSourceStatusByMediaId = vi.fn()
  })

  it("uses non-masked tablet drawers so chat remains visible", () => {
    render(<WorkspacePlayground />)

    expect(screen.getByTestId("workspace-drawer-left")).toHaveAttribute(
      "data-mask",
      "false"
    )
    expect(screen.getByTestId("workspace-drawer-right")).toHaveAttribute(
      "data-mask",
      "false"
    )
  })
})
