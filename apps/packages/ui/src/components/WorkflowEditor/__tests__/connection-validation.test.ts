import { describe, it, expect } from "vitest"
import type { WorkflowNode } from "@/types/workflow-editor"
import type { StepRegistry } from "../step-registry"
import { validateWorkflowConnection } from "../connection-validation"

const makeNode = (id: string, stepType: string): WorkflowNode => ({
  id,
  type: stepType,
  position: { x: 0, y: 0 },
  data: {
    label: stepType,
    stepType,
    config: {}
  }
})

const customRegistry: StepRegistry = {
  src_string: {
    type: "src_string",
    label: "String Source",
    description: "Produces strings",
    category: "text",
    icon: "FileText",
    color: "bg-cyan-500",
    inputs: [],
    outputs: [{ id: "out", label: "Out", dataType: "string" }],
    configSchema: []
  },
  dst_audio: {
    type: "dst_audio",
    label: "Audio Target",
    description: "Consumes audio",
    category: "audio",
    icon: "Headphones",
    color: "bg-teal-500",
    inputs: [{ id: "in", label: "In", dataType: "audio", required: true }],
    outputs: [],
    configSchema: []
  },
  dst_any: {
    type: "dst_any",
    label: "Any Target",
    description: "Consumes anything",
    category: "utility",
    icon: "Terminal",
    color: "bg-gray-500",
    inputs: [{ id: "in", label: "In", dataType: "any", required: true }],
    outputs: [],
    configSchema: []
  },
  src_control: {
    type: "src_control",
    label: "Control Source",
    description: "Produces control flow",
    category: "control",
    icon: "GitBranch",
    color: "bg-orange-500",
    inputs: [],
    outputs: [{ id: "out", label: "Out", dataType: "control" }],
    configSchema: []
  },
  dst_control: {
    type: "dst_control",
    label: "Control Target",
    description: "Consumes control flow",
    category: "control",
    icon: "GitBranch",
    color: "bg-orange-500",
    inputs: [{ id: "in", label: "In", dataType: "control", required: true }],
    outputs: [],
    configSchema: []
  }
}

describe("validateWorkflowConnection", () => {
  it("rejects self-connections", () => {
    const nodes = [makeNode("n1", "src_string")]
    const result = validateWorkflowConnection(
      { source: "n1", target: "n1", sourceHandle: "out", targetHandle: "out" },
      nodes,
      customRegistry
    )
    expect(result.valid).toBe(false)
    expect(result.reason).toContain("Cannot connect a node to itself")
  })

  it("allows compatible connections", () => {
    const nodes = [makeNode("n1", "src_string"), makeNode("n2", "dst_any")]
    const result = validateWorkflowConnection(
      { source: "n1", target: "n2", sourceHandle: "out", targetHandle: "in" },
      nodes,
      customRegistry
    )
    expect(result.valid).toBe(true)
  })

  it("rejects incompatible port types with guidance", () => {
    const nodes = [makeNode("n1", "src_string"), makeNode("n2", "dst_audio")]
    const result = validateWorkflowConnection(
      { source: "n1", target: "n2", sourceHandle: "out", targetHandle: "in" },
      nodes,
      customRegistry
    )
    expect(result.valid).toBe(false)
    expect(result.reason).toContain("Port type mismatch")
    expect(result.reason).toContain("string")
    expect(result.reason).toContain("audio")
  })

  it("enforces strict control-flow typing", () => {
    const nodes = [makeNode("n1", "src_control"), makeNode("n2", "dst_any")]
    const result = validateWorkflowConnection(
      { source: "n1", target: "n2", sourceHandle: "out", targetHandle: "in" },
      nodes,
      customRegistry
    )
    expect(result.valid).toBe(false)
  })

  it("allows control-to-control connections", () => {
    const nodes = [makeNode("n1", "src_control"), makeNode("n2", "dst_control")]
    const result = validateWorkflowConnection(
      { source: "n1", target: "n2", sourceHandle: "out", targetHandle: "in" },
      nodes,
      customRegistry
    )
    expect(result.valid).toBe(true)
  })
})

