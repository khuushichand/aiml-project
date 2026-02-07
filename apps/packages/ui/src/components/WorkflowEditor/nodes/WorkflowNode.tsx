/**
 * WorkflowNode Component
 *
 * Base node component for all workflow step types.
 * Renders the node with appropriate styling based on step type,
 * execution status, and selection state.
 */

import { memo, useMemo } from "react"
import { Handle, Position } from "@xyflow/react"
import type { NodeProps } from "@xyflow/react"
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Clock4,
  XCircle,
  Hand
} from "lucide-react"
import type {
  WorkflowNodeData,
  StepExecutionStatus
} from "@/types/workflow-editor"
import { useWorkflowEditorStore } from "@/store/workflow-editor"
import { getStepMetadata, PORT_COLORS } from "../step-registry"
import { STEP_ICON_COMPONENTS, DEFAULT_STEP_ICON } from "../step-icons"

type WorkflowNodeProps = NodeProps & {
  data: WorkflowNodeData
}

// Icon mapping (from registry icon keys)
const FALLBACK_ICON = DEFAULT_STEP_ICON

// Status icons
const STATUS_ICONS: Record<
  StepExecutionStatus,
  React.ComponentType<{ className?: string }>
> = {
  idle: Clock4,
  queued: Clock4,
  running: Loader2,
  success: CheckCircle2,
  failed: XCircle,
  skipped: XCircle,
  waiting_human: Hand,
  waiting_approval: Hand,
  cancelled: XCircle
}

// Status colors
const STATUS_COLORS: Record<StepExecutionStatus, string> = {
  idle: "text-gray-400",
  queued: "text-blue-400",
  running: "text-blue-500 animate-spin",
  success: "text-green-500",
  failed: "text-red-500",
  skipped: "text-gray-400",
  waiting_human: "text-yellow-500 animate-pulse",
  waiting_approval: "text-yellow-500 animate-pulse",
  cancelled: "text-gray-500"
}

// Category colors for node borders/backgrounds
const CATEGORY_STYLES: Record<string, { border: string; bg: string; header: string }> = {
  ai: {
    border: "border-purple-500",
    bg: "bg-purple-50 dark:bg-purple-950/30",
    header: "bg-purple-500"
  },
  data: {
    border: "border-blue-500",
    bg: "bg-blue-50 dark:bg-blue-950/30",
    header: "bg-blue-500"
  },
  control: {
    border: "border-orange-500",
    bg: "bg-orange-50 dark:bg-orange-950/30",
    header: "bg-orange-500"
  },
  io: {
    border: "border-green-500",
    bg: "bg-green-50 dark:bg-green-950/30",
    header: "bg-green-500"
  },
  utility: {
    border: "border-gray-500",
    bg: "bg-gray-50 dark:bg-gray-900/30",
    header: "bg-gray-500"
  }
}

export const WorkflowNode = memo(({ id, data, selected }: WorkflowNodeProps) => {
  const nodeStates = useWorkflowEditorStore((s) => s.nodeStates)
  const stepRegistry = useWorkflowEditorStore((s) => s.stepRegistry)
  const executionState = nodeStates[id]

  const metadata = useMemo(
    () => getStepMetadata(data.stepType, stepRegistry),
    [data.stepType, stepRegistry]
  )

  const Icon =
    (metadata?.icon && STEP_ICON_COMPONENTS[metadata.icon]) || FALLBACK_ICON
  const category = metadata?.category || "utility"
  const styles = CATEGORY_STYLES[category]

  const StatusIcon = executionState?.status
    ? STATUS_ICONS[executionState.status]
    : null

  const statusColor = executionState?.status
    ? STATUS_COLORS[executionState.status]
    : ""

  // Determine if node is running
  const isRunning = executionState?.status === "running"
  const isWaiting =
    executionState?.status === "waiting_human" ||
    executionState?.status === "waiting_approval"
  const hasError = executionState?.status === "failed"

  return (
    <div
      className={`
        relative rounded-lg border-2 shadow-md min-w-[180px] max-w-[280px]
        transition-all duration-200
        ${styles.border}
        ${styles.bg}
        ${selected ? "ring-2 ring-blue-400 ring-offset-2 dark:ring-offset-gray-900" : ""}
        ${isRunning ? "ring-2 ring-blue-400 animate-pulse" : ""}
        ${isWaiting ? "ring-2 ring-yellow-400" : ""}
        ${hasError ? "ring-2 ring-red-400" : ""}
      `}
    >
      {/* Header */}
      <div
        className={`
          flex items-center gap-2 px-3 py-2 rounded-t-md
          ${styles.header} text-white
        `}
      >
        <Icon className="w-4 h-4 shrink-0" />
        <span className="text-sm font-medium truncate flex-1">
          {data.label}
        </span>
        {StatusIcon && (
          <StatusIcon className={`w-4 h-4 shrink-0 ${statusColor}`} />
        )}
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        {/* Step type badge */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            {metadata?.label || data.stepType}
          </span>
        </div>

        {/* Streaming output preview (for prompt nodes) */}
        {executionState?.streamingOutput && (
          <div className="mt-2 p-2 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono max-h-20 overflow-y-auto">
            {executionState.streamingOutput.slice(-200)}
            {executionState.status === "running" && (
              <span className="animate-pulse">|</span>
            )}
          </div>
        )}

        {/* Error message */}
        {executionState?.error && (
          <div className="mt-2 p-2 bg-red-100 dark:bg-red-900/30 rounded text-xs text-red-600 dark:text-red-400 flex items-start gap-1">
            <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
            <span className="line-clamp-2">{executionState.error}</span>
          </div>
        )}

        {/* Duration */}
        {executionState?.durationMs && (
          <div className="mt-2 text-xs text-gray-400">
            {(executionState.durationMs / 1000).toFixed(2)}s
          </div>
        )}
      </div>

      {/* Input Handles */}
      {metadata?.inputs.map((input, idx) => (
        <Handle
          key={input.id}
          type="target"
          position={Position.Left}
          id={input.id}
          className={`
            !w-3 !h-3 !border-2 !border-white dark:!border-gray-800
            ${PORT_COLORS[input.dataType] || PORT_COLORS.any}
          `}
          style={{
            top: `${((idx + 1) / (metadata.inputs.length + 1)) * 100}%`
          }}
        />
      ))}

      {/* Output Handles */}
      {metadata?.outputs.map((output, idx) => (
        <Handle
          key={output.id}
          type="source"
          position={Position.Right}
          id={output.id}
          className={`
            !w-3 !h-3 !border-2 !border-white dark:!border-gray-800
            ${PORT_COLORS[output.dataType] || PORT_COLORS.any}
          `}
          style={{
            top: `${((idx + 1) / (metadata.outputs.length + 1)) * 100}%`
          }}
        />
      ))}
    </div>
  )
})

WorkflowNode.displayName = "WorkflowNode"

// Build node types map for React Flow registration
export const buildWorkflowNodeTypes = (stepTypes: string[] = []) => {
  const mapping: Record<string, typeof WorkflowNode> = {}
  stepTypes.forEach((type) => {
    mapping[type] = WorkflowNode
  })
  mapping.default = WorkflowNode
  return mapping
}
