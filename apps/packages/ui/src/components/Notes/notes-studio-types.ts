export type NotesStudioTemplateType = 'lined' | 'grid' | 'cornell'
export type NotesStudioHandwritingMode = 'off' | 'accented'
export type NotesStudioPaperSize = 'US Letter' | 'A4' | 'A5'

export interface NoteStudioLayoutPayload {
  template_type?: NotesStudioTemplateType
  handwriting_mode?: NotesStudioHandwritingMode
  render_version?: number
}

export type NoteStudioSectionKind = 'cue' | 'notes' | 'summary' | 'prompt' | string

export interface NoteStudioSectionPayload {
  id: string
  kind: NoteStudioSectionKind
  title?: string | null
  items?: string[] | null
  content?: string | null
}

export interface NoteStudioPayload {
  layout?: NoteStudioLayoutPayload | null
  sections?: NoteStudioSectionPayload[] | null
  [key: string]: unknown
}

export interface NoteStudioDiagramManifest {
  diagram_type?: string | null
  source_section_ids?: string[] | null
  source_graph?: unknown
  cached_svg?: string | null
  render_hash?: string | null
  generation_status?: string | null
  [key: string]: unknown
}

export interface NoteStudioDocumentSummary {
  note_id: string
  template_type: NotesStudioTemplateType
  handwriting_mode: NotesStudioHandwritingMode
  source_note_id?: string | null
  excerpt_hash?: string | null
  companion_content_hash?: string | null
  render_version: number
}

export interface NoteStudioDocument extends NoteStudioDocumentSummary {
  payload_json: NoteStudioPayload | Record<string, unknown>
  excerpt_snapshot?: string | null
  diagram_manifest_json?: NoteStudioDiagramManifest | Record<string, unknown> | null
  created_at: string
  last_modified: string
}

export interface NoteStudioNote {
  id: string
  title: string
  content: string
  studio?: NoteStudioDocumentSummary | null
  [key: string]: unknown
}

export interface NoteStudioState {
  note: NoteStudioNote
  studio_document: NoteStudioDocument
  is_stale: boolean
  stale_reason: string | null
}

export interface NoteStudioDeriveRequest {
  source_note_id: string
  excerpt_text: string
  template_type?: NotesStudioTemplateType
  handwriting_mode?: NotesStudioHandwritingMode
  provider?: string | null
  model?: string | null
}

export interface NoteStudioDiagramRequest {
  diagram_type?: string
  source_section_ids?: string[]
  provider?: string | null
  model?: string | null
}
