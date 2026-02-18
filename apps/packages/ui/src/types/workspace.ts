/**
 * Workspace Types
 * Types for the NotebookLM-style three-pane research interface
 */

// ─────────────────────────────────────────────────────────────────────────────
// Source Types
// ─────────────────────────────────────────────────────────────────────────────

export type WorkspaceSourceType =
  | "pdf"
  | "video"
  | "audio"
  | "website"
  | "document"
  | "text"

export type WorkspaceSourceStatus = "processing" | "ready" | "error"

export interface WorkspaceSource {
  id: string
  mediaId: number // Server-side media ID
  title: string
  type: WorkspaceSourceType
  status?: WorkspaceSourceStatus
  statusMessage?: string
  thumbnailUrl?: string
  addedAt: Date
  // Optional metadata
  url?: string
  fileSize?: number
  duration?: number // For audio/video in seconds
  pageCount?: number // For PDFs
}

// ─────────────────────────────────────────────────────────────────────────────
// Artifact Types
// ─────────────────────────────────────────────────────────────────────────────

export type ArtifactType =
  | "summary"
  | "audio_overview"
  | "mindmap"
  | "report"
  | "flashcards"
  | "quiz"
  | "timeline"
  | "slides"
  | "data_table"

export type ArtifactStatus = "pending" | "generating" | "completed" | "failed"

export interface GeneratedArtifact {
  id: string
  type: ArtifactType
  title: string
  status: ArtifactStatus
  serverId?: number | string // ID from outputs/quizzes/data-tables/slides endpoint
  content?: string // For text-based artifacts like summary, mindmap
  audioUrl?: string // For audio_overview - object URL to audio blob
  audioFormat?: string // Audio format (mp3, wav, etc.)
  presentationId?: string // For slides - ID of the generated presentation
  presentationVersion?: number // For slides - version for export
  errorMessage?: string // If status is failed
  data?: Record<string, unknown> // Optional structured artifact payload (quiz, flashcards, tables, etc.)
  createdAt: Date
  completedAt?: Date
}

// ─────────────────────────────────────────────────────────────────────────────
// Output Configuration Types
// ─────────────────────────────────────────────────────────────────────────────

export interface OutputTypeConfig {
  type: ArtifactType
  label: string
  icon: string // Lucide icon name
  description: string
  // API configuration
  endpoint?: string
  requiresSelectedSources?: boolean
}

export const OUTPUT_TYPES: OutputTypeConfig[] = [
  {
    type: "audio_overview",
    label: "Audio Overview",
    icon: "Headphones",
    description: "Generate a spoken summary of your sources",
    requiresSelectedSources: true
  },
  {
    type: "summary",
    label: "Summary",
    icon: "FileText",
    description: "Create a concise summary of key points",
    requiresSelectedSources: true
  },
  {
    type: "mindmap",
    label: "Mind Map",
    icon: "GitBranch",
    description: "Visualize concepts and relationships",
    requiresSelectedSources: true
  },
  {
    type: "report",
    label: "Report",
    icon: "FileSpreadsheet",
    description: "Generate a detailed report document",
    requiresSelectedSources: true
  },
  {
    type: "flashcards",
    label: "Flashcards",
    icon: "Layers",
    description: "Create study flashcards for review",
    requiresSelectedSources: true
  },
  {
    type: "quiz",
    label: "Quiz",
    icon: "HelpCircle",
    description: "Generate a quiz to test understanding",
    requiresSelectedSources: true
  },
  {
    type: "timeline",
    label: "Timeline",
    icon: "Calendar",
    description: "Create a chronological timeline",
    requiresSelectedSources: true
  },
  {
    type: "slides",
    label: "Slides",
    icon: "Presentation",
    description: "Generate presentation slides",
    requiresSelectedSources: true
  },
  {
    type: "data_table",
    label: "Data Table",
    icon: "Table",
    description: "Extract structured data into a table",
    requiresSelectedSources: true
  }
]

// ─────────────────────────────────────────────────────────────────────────────
// Workspace Configuration
// ─────────────────────────────────────────────────────────────────────────────

export interface WorkspaceConfig {
  id: string
  name: string
  tag: string // Format: "workspace:<slug>"
  createdAt: Date
  updatedAt: Date
}

// ─────────────────────────────────────────────────────────────────────────────
// Add Source Modal Types
// ─────────────────────────────────────────────────────────────────────────────

export type AddSourceTab = "upload" | "url" | "paste" | "search" | "existing"

export interface AddSourceModalState {
  open: boolean
  activeTab: AddSourceTab
  isProcessing: boolean
  error: string | null
}

// ─────────────────────────────────────────────────────────────────────────────
// UI State Types
// ─────────────────────────────────────────────────────────────────────────────

export interface WorkspaceUIState {
  leftPaneCollapsed: boolean
  rightPaneCollapsed: boolean
  sourceSearchQuery: string
  addSourceModalState: AddSourceModalState
}

// ─────────────────────────────────────────────────────────────────────────────
// Audio Generation Settings
// ─────────────────────────────────────────────────────────────────────────────

export type AudioTtsProvider = "browser" | "elevenlabs" | "openai" | "tldw"

export interface AudioGenerationSettings {
  provider: AudioTtsProvider
  model: string // e.g., "kokoro", "tts-1", "tts-1-hd"
  voice: string // e.g., "af_heart", "alloy"
  speed: number // 0.5 - 2.0
  format: "mp3" | "wav" | "opus" | "aac" | "flac"
}

export const DEFAULT_AUDIO_SETTINGS: AudioGenerationSettings = {
  provider: "tldw",
  model: "kokoro",
  voice: "af_heart",
  speed: 1.0,
  format: "mp3"
}

// ─────────────────────────────────────────────────────────────────────────────
// Workspace Note Types (for Quick Notes feature)
// ─────────────────────────────────────────────────────────────────────────────

export interface WorkspaceNote {
  id?: number // undefined = new note, number = existing note
  title: string
  content: string
  keywords: string[]
  version?: number // For optimistic locking on updates
  isDirty: boolean // Has unsaved changes
}

export const DEFAULT_WORKSPACE_NOTE: WorkspaceNote = {
  id: undefined,
  title: "",
  content: "",
  keywords: [],
  version: undefined,
  isDirty: false
}

// ─────────────────────────────────────────────────────────────────────────────
// Saved Workspaces (for workspace switcher)
// ─────────────────────────────────────────────────────────────────────────────

export interface SavedWorkspace {
  id: string
  name: string
  tag: string
  createdAt: Date
  lastAccessedAt: Date
  /** Number of sources in this workspace */
  sourceCount: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Slides/Presentation Types
// ─────────────────────────────────────────────────────────────────────────────

export type SlideLayout =
  | "title"
  | "content"
  | "two_column"
  | "quote"
  | "section"
  | "blank"

export interface Slide {
  order: number
  layout: SlideLayout
  title?: string
  content: string
  speaker_notes?: string
  metadata?: Record<string, unknown>
}

export interface PresentationResponse {
  id: string
  title: string
  description?: string
  theme: string
  slides: Slide[]
  version: number
  created_at: string
  last_modified: string
  deleted?: boolean
  source_type?: string
  source_ref?: string | number | string[] | null
}
