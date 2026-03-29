import { bgRequest } from '@/services/background-proxy'
import type { NoteStudioDeriveRequest, NoteStudioState } from '@/components/Notes/notes-studio-types'

export const deriveNoteStudio = async (
  payload: NoteStudioDeriveRequest
): Promise<NoteStudioState> => {
  return await bgRequest<NoteStudioState>({
    path: '/api/v1/notes/studio/derive' as any,
    method: 'POST' as any,
    headers: { 'Content-Type': 'application/json' },
    body: payload,
  })
}

export const getNoteStudioState = async (noteId: string): Promise<NoteStudioState> => {
  return await bgRequest<NoteStudioState>({
    path: `/api/v1/notes/${encodeURIComponent(noteId)}/studio` as any,
    method: 'GET' as any,
  })
}
