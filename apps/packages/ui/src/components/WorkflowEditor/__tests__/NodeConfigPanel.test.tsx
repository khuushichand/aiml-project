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

vi.mock("antd", async () => {
  const actual = await vi.importActual("antd")

  const FormItem = ({ label, children }: any) => (
    <div>
      {label ? <label>{label}</label> : null}
      {children}
    </div>
  )
  const Form = ({ children, ...rest }: any) => <div {...rest}>{children}</div>
  Form.Item = FormItem

  return {
    ...actual,
    Form,
    Select: ({ value, options = [], onChange, loading, notFoundContent, placeholder, ...rest }: any) => (
      <div data-testid="mock-select">
        <div
          data-testid="mock-select-trigger"
          role="combobox"
          onMouseDown={() => {}}
        >
          {loading && (!options || options.length === 0) ? notFoundContent : null}
        </div>
        <div data-testid="mock-select-options">
          {(options || []).map((opt: any) => (
            <div key={opt.value} role="option" onClick={() => onChange?.(opt.value)}>
              {opt.label}
            </div>
          ))}
        </div>
      </div>
    )
  }
})

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

    render(<NodeConfigPanel />)
    const trigger = screen.getByTestId("mock-select-trigger")
    expect(trigger).not.toBeNull()
    fireEvent.mouseDown(trigger)

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

    render(<NodeConfigPanel />)
    const trigger = screen.getByTestId("mock-select-trigger")
    expect(trigger).not.toBeNull()
    fireEvent.mouseDown(trigger)

    expect(await screen.findByText("GPT-4")).toBeInTheDocument()
    expect(await screen.findByText("GPT-4o Mini")).toBeInTheDocument()
  })

  it("exposes aria labels for icon-only node actions", () => {
    const schema: WorkflowStepSchema = {
      type: "object",
      properties: {
        model: { type: "string" }
      }
    }
    setupStore(schema)

    vi.mocked(useWorkflowDynamicOptions).mockReturnValue({
      optionsByKey: {},
      loadingByKey: {}
    })

    render(<NodeConfigPanel />)

    expect(
      screen.getByRole("button", { name: "Duplicate node" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Delete node" })
    ).toBeInTheDocument()
  })
})
