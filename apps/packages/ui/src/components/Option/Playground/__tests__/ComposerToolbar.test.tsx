import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { ComposerToolbar } from "../ComposerToolbar"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key
  })
}))

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock("@/components/Common/PromptSelect", () => ({
  PromptSelect: () => <div data-testid="prompt-select" />
}))

vi.mock("@/components/Common/CharacterSelect", () => ({
  CharacterSelect: () => <div data-testid="character-select" />
}))

vi.mock("@/components/Layouts/ConnectionStatus", () => ({
  ConnectionStatus: () => <div data-testid="connection-status" />
}))

vi.mock("@/components/Common/Button", () => ({
  Button: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  )
}))

vi.mock("../playground-features", () => ({
  ParameterPresets: () => <div data-testid="parameter-presets" />,
  SystemPromptTemplatesButton: () => <button type="button">Templates</button>,
  SessionCostEstimation: () => <div data-testid="session-cost" />
}))

vi.mock("../ComposerToolbarOverflow", () => ({
  ComposerToolbarOverflow: () => <div data-testid="toolbar-overflow" />
}))

const createProps = (
  overrides: Partial<React.ComponentProps<typeof ComposerToolbar>> = {}
): React.ComponentProps<typeof ComposerToolbar> => ({
  isProMode: false,
  isMobile: false,
  isConnectionReady: true,
  isSending: false,
  modelSelectButton: <button type="button">Model</button>,
  mcpControl: <button type="button">MCP</button>,
  sendControl: <button type="button">Send</button>,
  attachmentButton: <button type="button">Attach</button>,
  toolsButton: <button type="button">Tools</button>,
  voiceChatButton: null,
  modelUsageBadge: null,
  selectedSystemPrompt: undefined,
  setSelectedSystemPrompt: vi.fn(),
  setSelectedQuickPrompt: vi.fn(),
  temporaryChat: false,
  onToggleTemporaryChat: vi.fn(),
  privateChatLocked: false,
  isFireFoxPrivateMode: false,
  persistenceTooltip: "Persist",
  contextToolsOpen: false,
  onToggleKnowledgePanel: vi.fn(),
  webSearch: false,
  onToggleWebSearch: vi.fn(),
  hasWebSearch: true,
  onOpenModelSettings: vi.fn(),
  modelSummaryLabel: "Model",
  promptSummaryLabel: "Prompt",
  hasDictation: false,
  speechAvailable: false,
  speechUsesServer: false,
  isListening: false,
  isServerDictating: false,
  voiceChatEnabled: false,
  speechTooltip: "Dictation unavailable",
  onDictationToggle: vi.fn(),
  onTemplateSelect: vi.fn(),
  selectedModel: null,
  resolvedProviderKey: "openai",
  messages: [],
  selectedDocumentsCount: 0,
  uploadedFilesCount: 0,
  serverChatId: null,
  showServerPersistenceHint: false,
  onDismissServerPersistenceHint: vi.fn(),
  onFocusConnectionCard: vi.fn(),
  ...overrides
})

describe("ComposerToolbar web search", () => {
  it("renders MCP, then model/provider, then prompts in row 1", () => {
    render(<ComposerToolbar {...createProps()} />)

    const mcp = screen.getByText("MCP")
    const model = screen.getByText("Model")
    const prompt = screen.getByTestId("prompt-select")

    expect(
      mcp.compareDocumentPosition(model) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
    expect(
      model.compareDocumentPosition(prompt) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })

  it("invokes toggle callback when web search button is clicked", () => {
    const onToggleWebSearch = vi.fn()
    render(
      <ComposerToolbar
        {...createProps({ onToggleWebSearch, hasWebSearch: true, webSearch: false })}
      />
    )

    fireEvent.click(screen.getByTestId("web-search-toggle"))

    expect(onToggleWebSearch).toHaveBeenCalledTimes(1)
  })

  it("does not render web search button when capability is unavailable", () => {
    render(
      <ComposerToolbar
        {...createProps({ hasWebSearch: false })}
      />
    )

    expect(screen.queryByTestId("web-search-toggle")).toBeNull()
  })

  it("renders mode launcher, compare control, and context strip when provided", () => {
    const onClick = vi.fn()
    render(
      <ComposerToolbar
        {...createProps({
          modeLauncherButton: <button type="button">Modes</button>,
          compareControl: <button type="button">Compare</button>,
          contextItems: [
            {
              id: "model",
              label: "Model",
              value: "gpt-4.1",
              tone: "active",
              onClick
            }
          ]
        })}
      />
    )

    expect(screen.getByText("Modes")).toBeInTheDocument()
    expect(screen.getByText("Compare")).toBeInTheDocument()
    const contextStrip = screen.getByTestId("composer-context-strip")
    const modelChipButton = contextStrip.querySelector("button")
    expect(modelChipButton).not.toBeNull()
    fireEvent.click(modelChipButton as HTMLButtonElement)
    expect(onClick).toHaveBeenCalledTimes(1)
    expect(contextStrip).toBeInTheDocument()
  })
})
