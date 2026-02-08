import type { Connection } from "@xyflow/react"
import type { WorkflowNode, PortDataType } from "@/types/workflow-editor"
import type { StepRegistry, StepTypeMetadata } from "./step-registry"
import { getStepMetadata } from "./step-registry"

type ValidationResult = {
  valid: boolean
  reason?: string
}

const isPortTypeCompatible = (
  sourceType: PortDataType,
  targetType: PortDataType
): boolean => {
  // Control-flow links are intentionally strict.
  if (sourceType === "control" || targetType === "control") {
    return sourceType === "control" && targetType === "control"
  }
  if (sourceType === "any" || targetType === "any") return true
  return sourceType === targetType
}

const resolvePort = (
  metadata: StepTypeMetadata | undefined,
  portId: string | null | undefined,
  direction: "input" | "output"
) => {
  if (!metadata) return undefined
  const ports = direction === "input" ? metadata.inputs : metadata.outputs
  if (!Array.isArray(ports) || ports.length === 0) return undefined
  if (!portId) return ports[0]
  return ports.find((port) => port.id === portId) || ports[0]
}

export const validateWorkflowConnection = (
  connection: Connection,
  nodes: WorkflowNode[],
  stepRegistry: StepRegistry
): ValidationResult => {
  if (!connection.source || !connection.target) {
    return { valid: false, reason: "Connection is missing a source or target node." }
  }

  if (connection.source === connection.target) {
    return {
      valid: false,
      reason: "Cannot connect a node to itself. Connect to a different node."
    }
  }

  const sourceNode = nodes.find((node) => node.id === connection.source)
  const targetNode = nodes.find((node) => node.id === connection.target)
  if (!sourceNode || !targetNode) {
    return {
      valid: false,
      reason: "Connection references a node that is no longer available."
    }
  }

  const sourceMeta = getStepMetadata(sourceNode.data.stepType, stepRegistry)
  const targetMeta = getStepMetadata(targetNode.data.stepType, stepRegistry)
  const sourcePort = resolvePort(sourceMeta, connection.sourceHandle, "output")
  const targetPort = resolvePort(targetMeta, connection.targetHandle, "input")

  if (!sourcePort) {
    return {
      valid: false,
      reason: `Node "${sourceNode.data.label}" has no output port to connect from.`
    }
  }

  if (!targetPort) {
    return {
      valid: false,
      reason: `Node "${targetNode.data.label}" has no input port to connect to.`
    }
  }

  const compatible = isPortTypeCompatible(sourcePort.dataType, targetPort.dataType)
  if (!compatible) {
    return {
      valid: false,
      reason: `Port type mismatch: "${sourcePort.label}" outputs ${sourcePort.dataType}, but "${targetPort.label}" expects ${targetPort.dataType}.`
    }
  }

  return { valid: true }
}

