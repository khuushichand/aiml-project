export type NotesStudioTemplateType = 'lined' | 'grid' | 'cornell'
export type NotesStudioHandwritingMode = 'off' | 'accented'

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
  payload_json: Record<string, unknown>
  excerpt_snapshot?: string | null
  diagram_manifest_json?: Record<string, unknown> | null
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
