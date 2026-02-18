export type NoteListItem = {
  id: string | number
  title?: string
  content?: string
  updated_at?: string
  deleted?: boolean
  conversation_id?: string | null
  message_id?: string | null
  keywords?: string[]
  version?: number
}
