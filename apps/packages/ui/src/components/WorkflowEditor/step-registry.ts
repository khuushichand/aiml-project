/**
 * Step Type Registry
 *
 * Defines metadata, visual properties, and configuration schemas
 * for each workflow step type.
 */

import type {
  WorkflowStepType,
  StepCategory,
  ConfigFieldSchema,
  PortDefinition,
  WorkflowStepTypeInfo
} from "@/types/workflow-editor"

// Re-export for consumers
export type { StepCategory, ConfigFieldSchema, PortDefinition }

// Step type metadata definition
export interface StepTypeMetadata {
  type: WorkflowStepType
  label: string
  description: string
  category: StepCategory
  icon: string
  color: string
  inputs: PortDefinition[]
  outputs: PortDefinition[]
  configSchema: ConfigFieldSchema[]
}

// ─────────────────────────────────────────────────────────────────────────────
// Category Metadata
// ─────────────────────────────────────────────────────────────────────────────

export const STEP_CATEGORIES: Record<
  StepCategory,
  { label: string; color: string; order: number }
> = {
  ai: {
    label: "AI & LLM",
    color: "blue",
    order: 1
  },
  search: {
    label: "Search & RAG",
    color: "blue",
    order: 2
  },
  media: {
    label: "Media & Documents",
    color: "indigo",
    order: 3
  },
  text: {
    label: "Text & Data Transform",
    color: "cyan",
    order: 4
  },
  research: {
    label: "Research & Academic",
    color: "violet",
    order: 5
  },
  audio: {
    label: "Audio",
    color: "teal",
    order: 6
  },
  video: {
    label: "Video & Subtitles",
    color: "emerald",
    order: 7
  },
  control: {
    label: "Control Flow",
    color: "indigo",
    order: 8
  },
  io: {
    label: "Integrations",
    color: "green",
    order: 9
  },
  utility: {
    label: "Utility",
    color: "gray",
    order: 10
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step Type Registry
// ─────────────────────────────────────────────────────────────────────────────

export type StepRegistry = Record<string, StepTypeMetadata>

export const BASE_STEP_REGISTRY: StepRegistry = {
  // ─── AI Steps ────────────────────────────────────────────────────────────

  prompt: {
    type: "prompt",
    label: "LLM Prompt",
    description: "Generate text using a language model with templated prompts",
    category: "ai",
    icon: "MessageSquare",
    color: "bg-purple-500",
    inputs: [
      { id: "input", label: "Input", dataType: "any", required: true }
    ],
    outputs: [
      { id: "output", label: "Output", dataType: "string" }
    ],
    configSchema: [
      {
        key: "model",
        type: "model-picker",
        label: "Model",
        description: "Select the AI model to use",
        required: true
      },
      {
        key: "systemPrompt",
        type: "textarea",
        label: "System Prompt",
        description: "Instructions for the AI model",
        default: "You are a helpful assistant."
      },
      {
        key: "userPromptTemplate",
        type: "template-editor",
        label: "User Prompt Template",
        description: "Template for the user message. Use {{variable}} for placeholders.",
        required: true
      },
      {
        key: "temperature",
        type: "number",
        label: "Temperature",
        description: "Controls randomness (0-2)",
        default: 0.7,
        validation: { min: 0, max: 2 }
      },
      {
        key: "maxTokens",
        type: "number",
        label: "Max Tokens",
        description: "Maximum tokens to generate",
        default: 1024,
        validation: { min: 1, max: 128000 }
      }
    ]
  },

  rag_search: {
    type: "rag_search",
    label: "RAG Search",
    description: "Search your knowledge base for relevant documents",
    category: "search",
    icon: "Search",
    color: "bg-blue-500",
    inputs: [
      { id: "query", label: "Query", dataType: "string", required: true }
    ],
    outputs: [
      { id: "results", label: "Results", dataType: "array" }
    ],
    configSchema: [
      {
        key: "collectionId",
        type: "collection-picker",
        label: "Collection",
        description: "Select the knowledge collection to search",
        required: true
      },
      {
        key: "queryTemplate",
        type: "template-editor",
        label: "Query Template",
        description: "Template for the search query"
      },
      {
        key: "topK",
        type: "number",
        label: "Top K Results",
        description: "Number of results to return",
        default: 5,
        validation: { min: 1, max: 100 }
      },
      {
        key: "minScore",
        type: "number",
        label: "Minimum Score",
        description: "Minimum similarity score (0-1)",
        default: 0.5,
        validation: { min: 0, max: 1 }
      }
    ]
  },

  media_ingest: {
    type: "media_ingest",
    label: "Media Ingest",
    description: "Process YouTube videos, audio files, or other media",
    category: "media",
    icon: "Video",
    color: "bg-blue-600",
    inputs: [
      { id: "source", label: "Source", dataType: "any" }
    ],
    outputs: [
      { id: "content", label: "Content", dataType: "object" },
      { id: "transcript", label: "Transcript", dataType: "string" }
    ],
    configSchema: [
      {
        key: "sourceType",
        type: "select",
        label: "Source Type",
        default: "url",
        options: [
          { value: "url", label: "URL" },
          { value: "file", label: "File Upload" }
        ]
      },
      {
        key: "url",
        type: "url",
        label: "Media URL",
        description: "YouTube URL or direct media link",
        showWhen: { field: "sourceType", value: "url" }
      },
      {
        key: "extractAudio",
        type: "checkbox",
        label: "Extract Audio",
        default: true
      },
      {
        key: "transcribe",
        type: "checkbox",
        label: "Transcribe Audio",
        default: true
      },
      {
        key: "chunkingStrategy",
        type: "select",
        label: "Chunking Strategy",
        default: "paragraph",
        options: [
          { value: "sentence", label: "Sentence" },
          { value: "paragraph", label: "Paragraph" },
          { value: "fixed", label: "Fixed Size" }
        ]
      }
    ]
  },

  // ─── Control Flow Steps ──────────────────────────────────────────────────

  branch: {
    type: "branch",
    label: "Branch",
    description: "Conditional routing based on expressions",
    category: "control",
    icon: "GitBranch",
    color: "bg-orange-500",
    inputs: [
      { id: "input", label: "Input", dataType: "any", required: true }
    ],
    outputs: [
      { id: "true", label: "True", dataType: "control" },
      { id: "false", label: "False", dataType: "control" },
      { id: "default", label: "Default", dataType: "control" }
    ],
    configSchema: [
      {
        key: "conditions",
        type: "json-editor",
        label: "Conditions",
        description: "Array of condition objects with expression and outputId",
        default: [
          { id: "cond-1", expression: "input.value > 0", outputId: "true" }
        ]
      },
      {
        key: "defaultOutputId",
        type: "text",
        label: "Default Output",
        description: "Output to use when no conditions match",
        default: "false"
      }
    ]
  },

  map: {
    type: "map",
    label: "Map",
    description: "Process each item in an array (fan-out)",
    category: "control",
    icon: "Layers",
    color: "bg-orange-600",
    inputs: [
      { id: "array", label: "Array", dataType: "array", required: true }
    ],
    outputs: [
      { id: "item", label: "Item", dataType: "any" },
      { id: "results", label: "Results", dataType: "array" }
    ],
    configSchema: [
      {
        key: "arrayPath",
        type: "text",
        label: "Array Path",
        description: "JSON path to the array (e.g., input.items)",
        default: "input"
      },
      {
        key: "itemVariable",
        type: "text",
        label: "Item Variable",
        description: "Variable name for each item",
        default: "item"
      },
      {
        key: "maxParallel",
        type: "number",
        label: "Max Parallel",
        description: "Maximum concurrent executions",
        default: 5,
        validation: { min: 1, max: 50 }
      }
    ]
  },

  wait_for_human: {
    type: "wait_for_human",
    label: "Human Approval",
    description: "Pause workflow and wait for human approval",
    category: "control",
    icon: "UserCheck",
    color: "bg-yellow-500",
    inputs: [
      { id: "data", label: "Data", dataType: "any", required: true }
    ],
    outputs: [
      { id: "approved", label: "Approved", dataType: "any" },
      { id: "rejected", label: "Rejected", dataType: "any" }
    ],
    configSchema: [
      {
        key: "promptMessage",
        type: "textarea",
        label: "Approval Prompt",
        description: "Message shown to the reviewer",
        required: true
      },
      {
        key: "allowEdit",
        type: "checkbox",
        label: "Allow Editing",
        description: "Let reviewer edit data before approving",
        default: true
      },
      {
        key: "editableFields",
        type: "multiselect",
        label: "Editable Fields",
        description: "Fields the reviewer can edit",
        showWhen: { field: "allowEdit", value: true }
      },
      {
        key: "timeoutSeconds",
        type: "number",
        label: "Timeout (seconds)",
        description: "Auto-action after timeout (0 = no timeout)",
        default: 0,
        validation: { min: 0 }
      },
      {
        key: "defaultAction",
        type: "select",
        label: "Default Action",
        description: "Action to take on timeout",
        default: "reject",
        options: [
          { value: "approve", label: "Approve" },
          { value: "reject", label: "Reject" }
        ],
        showWhen: { field: "timeoutSeconds", value: 0 }
      }
    ]
  },

  // ─── I/O Steps ───────────────────────────────────────────────────────────

  webhook: {
    type: "webhook",
    label: "Webhook",
    description: "Make HTTP requests to external APIs",
    category: "io",
    icon: "Globe",
    color: "bg-green-500",
    inputs: [
      { id: "data", label: "Data", dataType: "any" }
    ],
    outputs: [
      { id: "response", label: "Response", dataType: "object" }
    ],
    configSchema: [
      {
        key: "url",
        type: "url",
        label: "URL",
        description: "The endpoint URL",
        required: true
      },
      {
        key: "method",
        type: "select",
        label: "Method",
        default: "POST",
        options: [
          { value: "GET", label: "GET" },
          { value: "POST", label: "POST" },
          { value: "PUT", label: "PUT" },
          { value: "PATCH", label: "PATCH" },
          { value: "DELETE", label: "DELETE" }
        ]
      },
      {
        key: "headers",
        type: "json-editor",
        label: "Headers",
        description: "Request headers as JSON object",
        default: { "Content-Type": "application/json" }
      },
      {
        key: "bodyTemplate",
        type: "template-editor",
        label: "Body Template",
        description: "Request body template with {{variables}}"
      },
      {
        key: "responseMapping",
        type: "text",
        label: "Response Mapping",
        description: "JSON path to extract from response"
      }
    ]
  },

  tts: {
    type: "tts",
    label: "Text to Speech",
    description: "Convert text to audio",
    category: "audio",
    icon: "Volume2",
    color: "bg-green-600",
    inputs: [
      { id: "text", label: "Text", dataType: "string", required: true }
    ],
    outputs: [
      { id: "audio", label: "Audio", dataType: "audio" }
    ],
    configSchema: [
      {
        key: "voice",
        type: "select",
        label: "Voice",
        default: "alloy",
        options: [
          { value: "alloy", label: "Alloy" },
          { value: "echo", label: "Echo" },
          { value: "fable", label: "Fable" },
          { value: "onyx", label: "Onyx" },
          { value: "nova", label: "Nova" },
          { value: "shimmer", label: "Shimmer" }
        ]
      },
      {
        key: "speed",
        type: "number",
        label: "Speed",
        default: 1.0,
        validation: { min: 0.25, max: 4.0 }
      },
      {
        key: "format",
        type: "select",
        label: "Output Format",
        default: "mp3",
        options: [
          { value: "mp3", label: "MP3" },
          { value: "opus", label: "OPUS" },
          { value: "aac", label: "AAC" },
          { value: "flac", label: "FLAC" },
          { value: "wav", label: "WAV" },
          { value: "pcm", label: "PCM (raw)" }
        ]
      }
    ]
  },

  stt_transcribe: {
    type: "stt_transcribe",
    label: "Transcribe",
    description: "Convert audio to text",
    category: "audio",
    icon: "Mic",
    color: "bg-green-700",
    inputs: [
      { id: "audio", label: "Audio", dataType: "audio", required: true }
    ],
    outputs: [
      { id: "text", label: "Text", dataType: "string" }
    ],
    configSchema: [
      {
        key: "model",
        type: "select",
        label: "Model",
        default: "whisper-1",
        options: [
          { value: "whisper-1", label: "Whisper" }
        ]
      },
      {
        key: "language",
        type: "text",
        label: "Language",
        description: "ISO language code (e.g., en, es, fr)"
      },
      {
        key: "punctuate",
        type: "checkbox",
        label: "Add Punctuation",
        default: true
      }
    ]
  },

  deep_research: {
    type: "deep_research",
    label: "Deep Research Run",
    description:
      "Launch a deep research session and return its run reference without waiting for completion",
    category: "research",
    icon: "FileSearch",
    color: "bg-violet-600",
    inputs: [{ id: "query", label: "Query", dataType: "string", required: true }],
    outputs: [{ id: "run", label: "Run", dataType: "object" }],
    configSchema: [
      {
        key: "query",
        type: "template-editor",
        label: "Query",
        description: "Templated research query resolved from workflow context",
        required: true
      },
      {
        key: "source_policy",
        type: "select",
        label: "Source Policy",
        description: "How local and external sources should be balanced",
        default: "balanced",
        options: [
          { value: "balanced", label: "Balanced" },
          { value: "local_first", label: "Local First" },
          { value: "external_first", label: "External First" },
          { value: "local_only", label: "Local Only" },
          { value: "external_only", label: "External Only" }
        ]
      },
      {
        key: "autonomy_mode",
        type: "select",
        label: "Autonomy Mode",
        description: "Whether the run pauses at checkpoints or runs autonomously",
        default: "checkpointed",
        options: [
          { value: "checkpointed", label: "Checkpointed" },
          { value: "autonomous", label: "Autonomous" }
        ]
      },
      {
        key: "limits_json",
        type: "json-editor",
        label: "Limits",
        description: "Optional run limits for the launched research session"
      },
      {
        key: "provider_overrides",
        type: "json-editor",
        label: "Provider Overrides",
        description: "Optional per-run provider override configuration"
      },
      {
        key: "save_artifact",
        type: "checkbox",
        label: "Save Artifact",
        description: "Persist deep_research_launch.json as a workflow artifact",
        default: true
      },
      {
        key: "timeout_seconds",
        type: "number",
        label: "Launch Timeout",
        description: "Bounds only the launch step, not the research session lifetime",
        validation: { min: 1 }
      }
    ]
  },

  deep_research_wait: {
    type: "deep_research_wait",
    label: "Deep Research Wait",
    description:
      "Wait for a launched deep research run to finish and optionally return the final bundle",
    category: "research",
    icon: "Clock",
    color: "bg-violet-700",
    inputs: [{ id: "run", label: "Run", dataType: "object", required: true }],
    outputs: [{ id: "result", label: "Result", dataType: "object" }],
    configSchema: [
      {
        key: "run_id",
        type: "template-editor",
        label: "Run ID",
        description: "Primary chaining field, typically {{ deep_research.run_id }}"
      },
      {
        key: "run",
        type: "json-editor",
        label: "Run",
        description: "Optional full launch output object containing run_id"
      },
      {
        key: "include_bundle",
        type: "checkbox",
        label: "Include Bundle",
        description: "Include the final bundle in step outputs when the run completes",
        default: true
      },
      {
        key: "fail_on_cancelled",
        type: "checkbox",
        label: "Fail on Cancelled",
        description: "Mark the step as failed when the research run is cancelled",
        default: true
      },
      {
        key: "fail_on_failed",
        type: "checkbox",
        label: "Fail on Failed",
        description: "Mark the step as failed when the research run fails",
        default: true
      },
      {
        key: "poll_interval_seconds",
        type: "number",
        label: "Poll Interval",
        description: "How often the workflow polls the research run for terminal status",
        default: 2,
        validation: { min: 0.1, max: 60 }
      },
      {
        key: "save_artifact",
        type: "checkbox",
        label: "Save Artifact",
        description: "Persist deep_research_wait.json as a workflow artifact",
        default: true
      },
      {
        key: "timeout_seconds",
        type: "number",
        label: "Wait Timeout",
        description: "Bounds how long the workflow waits for terminal research status",
        validation: { min: 1 }
      }
    ]
  },

  deep_research_load_bundle: {
    type: "deep_research_load_bundle",
    label: "Deep Research Load Bundle",
    description:
      "Loads references from a completed deep research run without returning the full bundle",
    category: "research",
    icon: "BookText",
    color: "bg-violet-800",
    inputs: [{ id: "run", label: "Run", dataType: "object", required: true }],
    outputs: [{ id: "result", label: "Result", dataType: "object" }],
    configSchema: [
      {
        key: "run_id",
        type: "template-editor",
        label: "Run ID",
        description: "Primary chaining field, typically {{ deep_research_wait.run_id }}"
      },
      {
        key: "run",
        type: "json-editor",
        label: "Run",
        description: "Optional full wait output object containing run_id"
      },
      {
        key: "save_artifact",
        type: "checkbox",
        label: "Save Artifact",
        description: "Persist deep_research_bundle_ref.json as a workflow artifact",
        default: true
      }
    ]
  },

  // ─── Utility Steps ───────────────────────────────────────────────────────

  delay: {
    type: "delay",
    label: "Delay",
    description: "Wait for a specified duration",
    category: "utility",
    icon: "Clock",
    color: "bg-gray-500",
    inputs: [
      { id: "input", label: "Input", dataType: "any" }
    ],
    outputs: [
      { id: "output", label: "Output", dataType: "any" }
    ],
    configSchema: [
      {
        key: "durationSeconds",
        type: "duration",
        label: "Duration",
        description: "Time to wait in seconds",
        default: 5,
        validation: { min: 0, max: 3600 }
      }
    ]
  },

  log: {
    type: "log",
    label: "Log",
    description: "Output debug information",
    category: "utility",
    icon: "Terminal",
    color: "bg-gray-600",
    inputs: [
      { id: "data", label: "Data", dataType: "any" }
    ],
    outputs: [
      { id: "passthrough", label: "Passthrough", dataType: "any" }
    ],
    configSchema: [
      {
        key: "level",
        type: "select",
        label: "Log Level",
        default: "info",
        options: [
          { value: "debug", label: "Debug" },
          { value: "info", label: "Info" },
          { value: "warn", label: "Warning" },
          { value: "error", label: "Error" }
        ]
      },
      {
        key: "messageTemplate",
        type: "template-editor",
        label: "Message Template",
        description: "Template for the log message"
      }
    ]
  },

  // ─── Start/End Steps ─────────────────────────────────────────────────────

  start: {
    type: "start",
    label: "Start",
    description: "Entry point of the workflow",
    category: "control",
    icon: "Play",
    color: "bg-emerald-500",
    inputs: [],
    outputs: [
      { id: "output", label: "Output", dataType: "any" }
    ],
    configSchema: [
      {
        key: "inputSchema",
        type: "json-editor",
        label: "Input Schema",
        description: "Define expected input structure"
      }
    ]
  },

  end: {
    type: "end",
    label: "End",
    description: "Exit point of the workflow",
    category: "control",
    icon: "Square",
    color: "bg-red-500",
    inputs: [
      { id: "input", label: "Input", dataType: "any", required: true }
    ],
    outputs: [],
    configSchema: [
      {
        key: "outputMapping",
        type: "text",
        label: "Output Mapping",
        description: "JSON path to extract as final output"
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

const DEFAULT_INPUT: PortDefinition = {
  id: "input",
  label: "Input",
  dataType: "any",
  required: false
}

const DEFAULT_OUTPUT: PortDefinition = {
  id: "output",
  label: "Output",
  dataType: "any"
}

const clonePorts = (ports: PortDefinition[]): PortDefinition[] =>
  ports.map((port) => ({ ...port }))

const CATEGORY_PORT_FALLBACKS: Record<
  StepCategory,
  { inputs: PortDefinition[]; outputs: PortDefinition[] }
> = {
  ai: {
    inputs: [{ id: "input", label: "Input", dataType: "any", required: true }],
    outputs: [{ id: "output", label: "Output", dataType: "string" }]
  },
  search: {
    inputs: [{ id: "query", label: "Query", dataType: "string", required: true }],
    outputs: [{ id: "results", label: "Results", dataType: "array" }]
  },
  media: {
    inputs: [{ id: "source", label: "Source", dataType: "file", required: true }],
    outputs: [{ id: "content", label: "Content", dataType: "object" }]
  },
  text: {
    inputs: [{ id: "text", label: "Text", dataType: "string", required: true }],
    outputs: [{ id: "text", label: "Text", dataType: "string" }]
  },
  research: {
    inputs: [{ id: "query", label: "Query", dataType: "string", required: true }],
    outputs: [{ id: "results", label: "Results", dataType: "array" }]
  },
  audio: {
    inputs: [{ id: "audio", label: "Audio", dataType: "audio", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  video: {
    inputs: [{ id: "video", label: "Video", dataType: "file", required: true }],
    outputs: [{ id: "video", label: "Video", dataType: "file" }]
  },
  control: {
    inputs: [{ id: "input", label: "Input", dataType: "any", required: true }],
    outputs: [{ id: "output", label: "Output", dataType: "control" }]
  },
  io: {
    inputs: [{ id: "payload", label: "Payload", dataType: "object", required: true }],
    outputs: [{ id: "result", label: "Result", dataType: "object" }]
  },
  utility: {
    inputs: [{ ...DEFAULT_INPUT }],
    outputs: [{ ...DEFAULT_OUTPUT }]
  }
}

const PORT_OVERRIDES: Record<
  string,
  { inputs: PortDefinition[]; outputs: PortDefinition[] }
> = {
  // Control flow
  start: {
    inputs: [],
    outputs: [{ id: "output", label: "Output", dataType: "any" }]
  },
  end: {
    inputs: [{ id: "input", label: "Input", dataType: "any", required: true }],
    outputs: []
  },
  branch: {
    inputs: [{ id: "input", label: "Input", dataType: "any", required: true }],
    outputs: [
      { id: "true", label: "True", dataType: "control" },
      { id: "false", label: "False", dataType: "control" },
      { id: "default", label: "Default", dataType: "control" }
    ]
  },
  map: {
    inputs: [{ id: "array", label: "Array", dataType: "array", required: true }],
    outputs: [
      { id: "item", label: "Item", dataType: "any" },
      { id: "results", label: "Results", dataType: "array" }
    ]
  },
  batch: {
    inputs: [{ id: "items", label: "Items", dataType: "array", required: true }],
    outputs: [{ id: "results", label: "Results", dataType: "array" }]
  },
  parallel: {
    inputs: [{ id: "inputs", label: "Inputs", dataType: "array", required: true }],
    outputs: [{ id: "results", label: "Results", dataType: "array" }]
  },
  wait_for_human: {
    inputs: [{ id: "data", label: "Data", dataType: "any", required: true }],
    outputs: [
      { id: "approved", label: "Approved", dataType: "any" },
      { id: "rejected", label: "Rejected", dataType: "any" }
    ]
  },
  wait_for_approval: {
    inputs: [{ id: "data", label: "Data", dataType: "any", required: true }],
    outputs: [
      { id: "approved", label: "Approved", dataType: "any" },
      { id: "rejected", label: "Rejected", dataType: "any" }
    ]
  },
  deep_research: {
    inputs: [{ id: "query", label: "Query", dataType: "string", required: true }],
    outputs: [{ id: "run", label: "Run", dataType: "object" }]
  },
  deep_research_wait: {
    inputs: [{ id: "run", label: "Run", dataType: "object", required: true }],
    outputs: [{ id: "result", label: "Result", dataType: "object" }]
  },
  deep_research_load_bundle: {
    inputs: [{ id: "run", label: "Run", dataType: "object", required: true }],
    outputs: [{ id: "result", label: "Result", dataType: "object" }]
  },
  // Audio
  tts: {
    inputs: [{ id: "text", label: "Text", dataType: "string", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  multi_voice_tts: {
    inputs: [{ id: "text", label: "Text", dataType: "string", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  stt_transcribe: {
    inputs: [{ id: "audio", label: "Audio", dataType: "audio", required: true }],
    outputs: [{ id: "text", label: "Text", dataType: "string" }]
  },
  audio_normalize: {
    inputs: [{ id: "audio", label: "Audio", dataType: "audio", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  audio_concat: {
    inputs: [{ id: "tracks", label: "Tracks", dataType: "array", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  audio_trim: {
    inputs: [{ id: "audio", label: "Audio", dataType: "audio", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  audio_convert: {
    inputs: [{ id: "audio", label: "Audio", dataType: "audio", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  audio_extract: {
    inputs: [{ id: "source", label: "Source", dataType: "file", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  audio_mix: {
    inputs: [{ id: "tracks", label: "Tracks", dataType: "array", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  audio_diarize: {
    inputs: [{ id: "audio", label: "Audio", dataType: "audio", required: true }],
    outputs: [{ id: "segments", label: "Segments", dataType: "array" }]
  },
  audio_briefing_compose: {
    inputs: [{ id: "content", label: "Content", dataType: "string", required: true }],
    outputs: [{ id: "audio", label: "Audio", dataType: "audio" }]
  },
  // Video
  video_trim: {
    inputs: [{ id: "video", label: "Video", dataType: "file", required: true }],
    outputs: [{ id: "video", label: "Video", dataType: "file" }]
  },
  video_concat: {
    inputs: [{ id: "clips", label: "Clips", dataType: "array", required: true }],
    outputs: [{ id: "video", label: "Video", dataType: "file" }]
  },
  video_convert: {
    inputs: [{ id: "video", label: "Video", dataType: "file", required: true }],
    outputs: [{ id: "video", label: "Video", dataType: "file" }]
  },
  video_thumbnail: {
    inputs: [{ id: "video", label: "Video", dataType: "file", required: true }],
    outputs: [{ id: "image", label: "Image", dataType: "file" }]
  },
  video_extract_frames: {
    inputs: [{ id: "video", label: "Video", dataType: "file", required: true }],
    outputs: [{ id: "frames", label: "Frames", dataType: "array" }]
  },
  subtitle_generate: {
    inputs: [{ id: "audio", label: "Audio", dataType: "audio", required: true }],
    outputs: [{ id: "subtitles", label: "Subtitles", dataType: "string" }]
  },
  subtitle_translate: {
    inputs: [{ id: "subtitles", label: "Subtitles", dataType: "string", required: true }],
    outputs: [{ id: "translated", label: "Translated", dataType: "string" }]
  },
  subtitle_burn: {
    inputs: [
      { id: "video", label: "Video", dataType: "file", required: true },
      { id: "subtitles", label: "Subtitles", dataType: "string", required: true }
    ],
    outputs: [{ id: "video", label: "Video", dataType: "file" }]
  },
  // Search
  rag_search: {
    inputs: [{ id: "query", label: "Query", dataType: "string", required: true }],
    outputs: [{ id: "results", label: "Results", dataType: "array" }]
  },
  web_search: {
    inputs: [{ id: "query", label: "Query", dataType: "string", required: true }],
    outputs: [{ id: "results", label: "Results", dataType: "array" }]
  },
  embed: {
    inputs: [{ id: "text", label: "Text", dataType: "string", required: true }],
    outputs: [{ id: "embedding", label: "Embedding", dataType: "array" }]
  },
  rerank: {
    inputs: [
      { id: "query", label: "Query", dataType: "string", required: true },
      { id: "documents", label: "Documents", dataType: "array", required: true }
    ],
    outputs: [{ id: "ranked", label: "Ranked", dataType: "array" }]
  },
  // Media
  media_ingest: {
    inputs: [{ id: "source", label: "Source", dataType: "any" }],
    outputs: [
      { id: "content", label: "Content", dataType: "object" },
      { id: "transcript", label: "Transcript", dataType: "string" }
    ]
  },
  pdf_extract: {
    inputs: [{ id: "file", label: "File", dataType: "file", required: true }],
    outputs: [{ id: "text", label: "Text", dataType: "string" }]
  },
  ocr: {
    inputs: [{ id: "image", label: "Image", dataType: "file", required: true }],
    outputs: [{ id: "text", label: "Text", dataType: "string" }]
  }
}

const CATEGORY_COLOR_CLASSES: Record<StepCategory, string> = {
  ai: "bg-blue-500",
  search: "bg-blue-500",
  media: "bg-indigo-500",
  text: "bg-cyan-500",
  research: "bg-violet-500",
  audio: "bg-teal-500",
  video: "bg-emerald-500",
  control: "bg-indigo-500",
  io: "bg-green-500",
  utility: "bg-gray-500"
}

export const CATEGORY_OVERRIDES: Record<string, StepCategory> = {
  // AI & LLM (22 types)
  prompt: "ai",
  llm: "ai",
  llm_with_tools: "ai",
  llm_compare: "ai",
  llm_critique: "ai",
  summarize: "ai",
  image_gen: "ai",
  image_describe: "ai",
  translate: "ai",
  voice_intent: "ai",
  flashcard_generate: "ai",
  quiz_generate: "ai",
  quiz_evaluate: "ai",
  outline_generate: "ai",
  glossary_extract: "ai",
  mindmap_generate: "ai",
  report_generate: "ai",
  newsletter_generate: "ai",
  slides_generate: "ai",
  diagram_generate: "ai",
  literature_review: "ai",
  moderation: "ai",

  // Search & RAG (11 types)
  rag_search: "search",
  web_search: "search",
  query_expand: "search",
  query_rewrite: "search",
  hyde_generate: "search",
  semantic_cache_check: "search",
  search_aggregate: "search",
  rerank: "search",
  embed: "search",
  rss_fetch: "search",
  atom_fetch: "search",

  // Media & Documents (11 types)
  media_ingest: "media",
  process_media: "media",
  pdf_extract: "media",
  ocr: "media",
  document_table_extract: "media",
  chunking: "media",
  claims_extract: "media",
  citations: "media",
  bibliography_generate: "media",
  document_merge: "media",
  document_diff: "media",

  // Text & Data Transform (16 types)
  json_transform: "text",
  json_validate: "text",
  csv_to_json: "text",
  json_to_csv: "text",
  regex_extract: "text",
  text_clean: "text",
  xml_transform: "text",
  template_render: "text",
  markdown_to_html: "text",
  html_to_markdown: "text",
  keyword_extract: "text",
  sentiment_analyze: "text",
  language_detect: "text",
  topic_model: "text",
  entity_extract: "text",
  context_build: "text",

  // Research & Academic (10 types)
  deep_research: "research",
  deep_research_wait: "research",
  deep_research_load_bundle: "research",
  arxiv_search: "research",
  arxiv_download: "research",
  pubmed_search: "research",
  semantic_scholar_search: "research",
  google_scholar_search: "research",
  patent_search: "research",
  doi_resolve: "research",
  reference_parse: "research",
  bibtex_generate: "research",

  // Audio (11 types)
  tts: "audio",
  multi_voice_tts: "audio",
  stt_transcribe: "audio",
  audio_normalize: "audio",
  audio_concat: "audio",
  audio_trim: "audio",
  audio_convert: "audio",
  audio_extract: "audio",
  audio_mix: "audio",
  audio_diarize: "audio",
  audio_briefing_compose: "audio",

  // Video & Subtitles (8 types)
  video_trim: "video",
  video_concat: "video",
  video_convert: "video",
  video_thumbnail: "video",
  video_extract_frames: "video",
  subtitle_generate: "video",
  subtitle_translate: "video",
  subtitle_burn: "video",

  // Control Flow (10 types)
  acp_stage: "control",
  branch: "control",
  map: "control",
  batch: "control",
  parallel: "control",
  retry: "control",
  cache_result: "control",
  checkpoint: "control",
  workflow_call: "control",
  wait_for_human: "control",
  wait_for_approval: "control",

  // Integrations (16 types)
  webhook: "io",
  notify: "io",
  kanban: "io",
  s3_upload: "io",
  s3_download: "io",
  github_create_issue: "io",
  email_send: "io",
  screenshot_capture: "io",
  podcast_rss_publish: "io",
  mcp_tool: "io",
  chatbooks: "io",
  character_chat: "io",
  notes: "io",
  prompts: "io",
  collections: "io",
  evaluations: "io",
  schedule_workflow: "io",

  // Utility (10 types)
  delay: "utility",
  log: "utility",
  token_count: "utility",
  context_window_check: "utility",
  policy_check: "utility",
  diff_change_detector: "utility",
  sandbox_exec: "utility",
  timing_start: "utility",
  timing_stop: "utility",
  eval_readability: "utility"
}

export const ICON_OVERRIDES: Record<string, string> = {
  // AI & LLM
  prompt: "MessageSquare",
  llm: "MessageSquare",
  llm_with_tools: "Wrench",
  llm_compare: "GitCompareArrows",
  llm_critique: "ShieldCheck",
  summarize: "FileText",
  image_gen: "Image",
  image_describe: "Image",
  translate: "Languages",
  voice_intent: "AudioLines",
  flashcard_generate: "ClipboardList",
  quiz_generate: "ListChecks",
  quiz_evaluate: "CheckCircle2",
  outline_generate: "ListTree",
  glossary_extract: "BookOpen",
  mindmap_generate: "Share2",
  report_generate: "ScrollText",
  newsletter_generate: "Newspaper",
  slides_generate: "Presentation",
  diagram_generate: "GitBranch",
  literature_review: "BookOpen",
  moderation: "ShieldAlert",

  // Search & RAG
  rag_search: "Search",
  web_search: "Globe",
  query_expand: "Sparkles",
  query_rewrite: "RefreshCcw",
  hyde_generate: "Sparkles",
  semantic_cache_check: "Database",
  search_aggregate: "Combine",
  rerank: "ArrowUpDown",
  embed: "Database",
  rss_fetch: "Rss",
  atom_fetch: "Rss",

  // Media & Documents
  media_ingest: "Video",
  process_media: "FileText",
  pdf_extract: "FileText",
  ocr: "ScanSearch",
  document_table_extract: "Table2",
  chunking: "Scissors",
  claims_extract: "ScanSearch",
  citations: "Quote",
  bibliography_generate: "BookMarked",
  document_merge: "Merge",
  document_diff: "FileDiff",

  // Text & Data Transform
  json_transform: "Braces",
  json_validate: "ShieldCheck",
  csv_to_json: "Table2",
  json_to_csv: "Table2",
  regex_extract: "Regex",
  text_clean: "Eraser",
  xml_transform: "FileCode",
  template_render: "Code2",
  markdown_to_html: "Code2",
  html_to_markdown: "FileText",
  keyword_extract: "Tags",
  sentiment_analyze: "Smile",
  language_detect: "Languages",
  topic_model: "PieChart",
  entity_extract: "ScanSearch",
  context_build: "Layers",

  // Research & Academic
  deep_research: "FileSearch",
  deep_research_wait: "Clock",
  deep_research_load_bundle: "BookText",
  arxiv_search: "GraduationCap",
  arxiv_download: "Download",
  pubmed_search: "FlaskConical",
  semantic_scholar_search: "GraduationCap",
  google_scholar_search: "GraduationCap",
  patent_search: "FileSearch",
  doi_resolve: "Link",
  reference_parse: "BookText",
  bibtex_generate: "BookMarked",

  // Audio
  tts: "Volume2",
  multi_voice_tts: "AudioLines",
  stt_transcribe: "Mic",
  audio_normalize: "SlidersHorizontal",
  audio_concat: "Combine",
  audio_trim: "Scissors",
  audio_convert: "RefreshCcw",
  audio_extract: "Headphones",
  audio_mix: "Blend",
  audio_diarize: "Mic2",
  audio_briefing_compose: "Newspaper",

  // Video & Subtitles
  video_trim: "Scissors",
  video_concat: "Combine",
  video_convert: "MonitorPlay",
  video_thumbnail: "Image",
  video_extract_frames: "Film",
  subtitle_generate: "Captions",
  subtitle_translate: "Languages",
  subtitle_burn: "Captions",

  // Control Flow
  acp_stage: "Bot",
  branch: "GitBranch",
  map: "Layers",
  batch: "Layers",
  parallel: "SplitSquareHorizontal",
  wait_for_human: "UserCheck",
  wait_for_approval: "BadgeCheck",
  workflow_call: "GitBranch",
  cache_result: "Database",
  retry: "RotateCcw",
  checkpoint: "Save",

  // Integrations
  webhook: "Globe",
  notify: "Bell",
  kanban: "LayoutList",
  s3_upload: "CloudUpload",
  s3_download: "CloudDownload",
  github_create_issue: "Github",
  email_send: "Mail",
  screenshot_capture: "Camera",
  podcast_rss_publish: "Rss",
  mcp_tool: "Cpu",
  chatbooks: "BookOpen",
  character_chat: "Bot",
  notes: "NotebookPen",
  prompts: "MessageSquare",
  collections: "Library",
  evaluations: "BarChart",
  schedule_workflow: "Calendar",

  // Utility
  delay: "Clock",
  log: "Terminal",
  token_count: "Hash",
  context_window_check: "Gauge",
  policy_check: "ShieldAlert",
  diff_change_detector: "GitCompareArrows",
  sandbox_exec: "Terminal",
  timing_start: "Timer",
  timing_stop: "TimerOff",
  eval_readability: "BarChart",

  // Start/End
  start: "Play",
  end: "Square"
}

export const humanizeStepType = (value: string): string => {
  if (!value) return "Workflow Step"
  const TOKEN_OVERRIDES: Record<string, string> = {
    llm: "LLM"
  }

  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((token) => {
      const lower = token.toLowerCase()
      if (TOKEN_OVERRIDES[lower]) return TOKEN_OVERRIDES[lower]
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    })
    .join(" ")
}

export const resolveStepCategory = (stepType: string): StepCategory => {
  if (CATEGORY_OVERRIDES[stepType]) return CATEGORY_OVERRIDES[stepType]
  // Heuristic fallbacks for unknown step types
  if (stepType.includes("llm") || stepType.includes("_generate") || stepType.includes("summarize")) return "ai"
  if (stepType.includes("search") || stepType.includes("rag") || stepType.includes("embed") || stepType.includes("rerank")) return "search"
  if (stepType.includes("audio") || stepType.includes("tts") || stepType.includes("stt")) return "audio"
  if (stepType.includes("video") || stepType.includes("subtitle")) return "video"
  if (stepType.includes("media") || stepType.includes("pdf") || stepType.includes("ocr") || stepType.includes("document")) return "media"
  if (stepType.includes("json") || stepType.includes("csv") || stepType.includes("regex") || stepType.includes("text") || stepType.includes("xml")) return "text"
  if (stepType.includes("arxiv") || stepType.includes("pubmed") || stepType.includes("scholar") || stepType.includes("patent") || stepType.includes("doi")) return "research"
  if (stepType.includes("wait_for_") || stepType.includes("branch") || stepType.includes("map") || stepType.includes("batch")) return "control"
  if (stepType.includes("webhook") || stepType.includes("notify") || stepType.includes("email") || stepType.includes("s3_")) return "io"
  return "utility"
}

export const resolveStepIcon = (stepType: string): string =>
  ICON_OVERRIDES[stepType] || "MessageSquare"

export const resolveStepPorts = (stepType: string): {
  inputs: PortDefinition[]
  outputs: PortDefinition[]
} => {
  const override = PORT_OVERRIDES[stepType]
  if (override) {
    return {
      inputs: clonePorts(override.inputs),
      outputs: clonePorts(override.outputs)
    }
  }

  const categoryFallback = CATEGORY_PORT_FALLBACKS[resolveStepCategory(stepType)]
  if (categoryFallback) {
    return {
      inputs: clonePorts(categoryFallback.inputs),
      outputs: clonePorts(categoryFallback.outputs)
    }
  }

  return {
    inputs: [{ ...DEFAULT_INPUT }],
    outputs: [{ ...DEFAULT_OUTPUT }]
  }
}

export const createFallbackMetadata = (
  type: string,
  description?: string
): StepTypeMetadata => {
  const ports = resolveStepPorts(type)
  const category = resolveStepCategory(type)
  return {
    type,
    label: humanizeStepType(type),
    description: description || "Server-provided workflow step",
    category,
    icon: resolveStepIcon(type),
    color: CATEGORY_COLOR_CLASSES[category] || "bg-gray-500",
    inputs: ports.inputs,
    outputs: ports.outputs,
    configSchema: []
  }
}

export const buildStepRegistry = (
  serverSteps: WorkflowStepTypeInfo[] = []
): StepRegistry => {
  const registry: StepRegistry = { ...BASE_STEP_REGISTRY }
  for (const step of serverSteps) {
    const name = step.name
    if (!name) continue
    const existing = registry[name]
    if (existing) {
      registry[name] = {
        ...existing,
        description: step.description || existing.description,
        label: existing.label || humanizeStepType(name)
      }
      continue
    }
    registry[name] = createFallbackMetadata(name, step.description)
  }
  return registry
}

export const getStepMetadata = (
  type: WorkflowStepType,
  registry: StepRegistry = BASE_STEP_REGISTRY
): StepTypeMetadata | undefined =>
  registry[type] || createFallbackMetadata(type)

export const getStepsByCategory = (
  category: StepCategory,
  registry: StepRegistry = BASE_STEP_REGISTRY
): StepTypeMetadata[] =>
  Object.values(registry).filter((step) => step.category === category)

export const getAllSteps = (
  registry: StepRegistry = BASE_STEP_REGISTRY
): StepTypeMetadata[] => Object.values(registry)

export const getAddableSteps = (
  registry: StepRegistry = BASE_STEP_REGISTRY
): StepTypeMetadata[] =>
  Object.values(registry).filter(
    (step) => step.type !== "start" && step.type !== "end"
  )

export const getCategorizedSteps = (
  registry: StepRegistry = BASE_STEP_REGISTRY
): Array<{
  category: StepCategory
  label: string
  color: string
  steps: StepTypeMetadata[]
}> => {
  const categories = Object.entries(STEP_CATEGORIES)
    .sort((a, b) => a[1].order - b[1].order)
    .map(([key, meta]) => ({
      category: key as StepCategory,
      label: meta.label,
      color: meta.color,
      steps: getStepsByCategory(key as StepCategory, registry).filter(
        (s) => s.type !== "start" && s.type !== "end"
      )
    }))
    .filter((cat) => cat.steps.length > 0)

  return categories
}

// Data type colors for ports
export const PORT_COLORS: Record<string, string> = {
  any: "bg-gray-400",
  string: "bg-blue-400",
  number: "bg-green-400",
  boolean: "bg-yellow-400",
  array: "bg-purple-400",
  object: "bg-pink-400",
  file: "bg-orange-400",
  audio: "bg-cyan-400",
  control: "bg-gray-600"
}
