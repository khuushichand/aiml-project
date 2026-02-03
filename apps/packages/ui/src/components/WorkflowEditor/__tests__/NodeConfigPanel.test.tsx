import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, cleanup } from "@testing-library/react"
import NodeConfigPanel from "../NodeConfigPanel"
import { useWorkflowEditorStore } from "@/store/workflow-editor"
import { buildStepRegistry } from "../step-registry"
import type { WorkflowStepSchema } from "@/types/workflow-editor"
import { useWorkflowDynamicOptions } from "../dynamic-options"

vi.mock("../dynamic-options", () => ({
  useWorkflowDynamicOptions: vi.fn()
}))

const setupStore = (schema: WorkflowStepSchema) => {
  useWorkflowEditorStore.setState({
    nodes: [
      {
        id: "node-1",
        type: "llm",
        position: { x: 0, y: 0 },
        data: {
          label: "LLM",
          stepType: "llm",
          config: {}
        }
      }
    ],
    edges: [],
    selectedNodeIds: ["node-1"],
    stepRegistry: buildStepRegistry([]),
    stepSchemas: { llm: schema }
  })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  useWorkflowEditorStore.setState({
    nodes: [],
    edges: [],
    selectedNodeIds: [],
    stepSchemas: {},
    stepRegistry: buildStepRegistry([])
  })
})

describe("NodeConfigPanel selectors", () => {
  it("shows loading state for dynamic select options", async () => {
    const schema: WorkflowStepSchema = {
      type: "object",
      properties: {
        model: { type: "string" }
      }
    }
    setupStore(schema)

    vi.mocked(useWorkflowDynamicOptions).mockReturnValue({
      optionsByKey: {},
      loadingByKey: { model: true }
    })

    const { container } = render(<NodeConfigPanel />)
    const trigger = container.querySelector(".ant-select-selector")
    expect(trigger).not.toBeNull()
    fireEvent.mouseDown(trigger as Element)

    expect(await screen.findByText("Loading options...")).toBeInTheDocument()
  })

  it("renders provided options in the select dropdown", async () => {
    const schema: WorkflowStepSchema = {
      type: "object",
      properties: {
        model: { type: "string" }
      }
    }
    setupStore(schema)

    vi.mocked(useWorkflowDynamicOptions).mockReturnValue({
      optionsByKey: {
        model: [
          { value: "gpt-4", label: "GPT-4" },
          { value: "gpt-4o-mini", label: "GPT-4o Mini" }
        ]
      },
      loadingByKey: {}
    })

    const { container } = render(<NodeConfigPanel />)
    const trigger = container.querySelector(".ant-select-selector")
    expect(trigger).not.toBeNull()
    fireEvent.mouseDown(trigger as Element)

    expect(await screen.findByText("GPT-4")).toBeInTheDocument()
    expect(await screen.findByText("GPT-4o Mini")).toBeInTheDocument()
  })
})
