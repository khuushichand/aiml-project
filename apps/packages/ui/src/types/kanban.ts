/**
 * TypeScript types for Kanban API
 * Matches the tldw_server2 kanban_schemas.py
 */

// Priority type
export type PriorityType = "low" | "medium" | "high" | "urgent"

// Pagination
export interface PaginationInfo {
  total: number
  limit: number
  offset: number
  has_more: boolean
}

// =============================================================================
// Label Types
// =============================================================================

export interface Label {
  id: number
  uuid: string
  board_id: number
  name: string
  color: string
  created_at: string
  updated_at: string
}

export interface LabelCreate {
  name: string
  color: string
  client_id: string
}

export interface LabelUpdate {
  name?: string
  color?: string
}

// =============================================================================
// Board Types
// =============================================================================

export interface Board {
  id: number
  uuid: string
  name: string
  description?: string | null
  user_id: string
  client_id: string
  archived: boolean
  archived_at?: string | null
  activity_retention_days?: number | null
  created_at: string
  updated_at: string
  deleted: boolean
  deleted_at?: string | null
  version: number
  metadata?: Record<string, any> | null
}

export interface BoardCreate {
  name: string
  description?: string
  client_id: string
  activity_retention_days?: number
  metadata?: Record<string, any>
}

export interface BoardUpdate {
  name?: string
  description?: string
  activity_retention_days?: number
  metadata?: Record<string, any>
}

export interface BoardListResponse {
  boards: Board[]
  pagination: PaginationInfo
}

// =============================================================================
// List Types
// =============================================================================

export interface KanbanList {
  id: number
  uuid: string
  name: string
  board_id: number
  client_id: string
  position: number
  archived: boolean
  archived_at?: string | null
  created_at: string
  updated_at: string
  deleted: boolean
  deleted_at?: string | null
  version: number
  card_count?: number | null
}

export interface ListCreate {
  name: string
  client_id: string
  position?: number
}

export interface ListUpdate {
  name?: string
}

export interface ListsListResponse {
  lists: KanbanList[]
}

// =============================================================================
// Card Types
// =============================================================================

export interface Card {
  id: number
  uuid: string
  title: string
  description?: string | null
  board_id: number
  list_id: number
  client_id: string
  position: number
  due_date?: string | null
  due_complete: boolean
  start_date?: string | null
  priority?: PriorityType | null
  archived: boolean
  archived_at?: string | null
  created_at: string
  updated_at: string
  deleted: boolean
  deleted_at?: string | null
  version: number
  metadata?: Record<string, any> | null
  // Fields from backend GET /boards/{id} nested response
  labels?: Label[]
  checklist_count?: number
  checklist_complete?: number
  checklist_total?: number
  comment_count?: number
}

export interface CardCreate {
  title: string
  client_id: string
  description?: string
  position?: number
  due_date?: string
  start_date?: string
  priority?: PriorityType
  metadata?: Record<string, any>
}

export interface CardUpdate {
  title?: string
  description?: string | null
  due_date?: string | null
  due_complete?: boolean
  start_date?: string | null
  priority?: PriorityType | null
  metadata?: Record<string, any>
}

export interface CardsListResponse {
  cards: Card[]
}

export interface CardMoveRequest {
  target_list_id: number
  position?: number
}

// =============================================================================
// Nested Response Types (for GET /boards/{id})
// =============================================================================

export interface ListWithCards extends KanbanList {
  cards: Card[]
}

export interface BoardWithLists extends Board {
  lists: ListWithCards[]
  total_cards: number
}

// =============================================================================
// Reorder Types
// =============================================================================

export interface ReorderRequest {
  ids: number[]
}

export interface ReorderResponse {
  success: boolean
  message?: string
}

// =============================================================================
// Checklist Types
// =============================================================================

export interface Checklist {
  id: number
  uuid: string
  card_id: number
  title: string
  position: number
  created_at: string
  updated_at: string
}

export interface ChecklistItem {
  id: number
  uuid: string
  checklist_id: number
  content: string
  checked: boolean
  position: number
  created_at: string
  updated_at: string
}

export interface ChecklistWithItems extends Checklist {
  items: ChecklistItem[]
}

// =============================================================================
// Comment Types
// =============================================================================

export interface Comment {
  id: number
  uuid: string
  card_id: number
  user_id: string
  content: string
  created_at: string
  updated_at: string
}

// =============================================================================
// Import/Export Types
// =============================================================================

export interface BoardImportRequest {
  data: Record<string, any>
  board_name?: string
}

export interface ImportStats {
  board_id: number
  lists_imported: number
  cards_imported: number
  labels_imported: number
  checklists_imported: number
  checklist_items_imported: number
  comments_imported: number
}

export interface BoardImportResponse {
  board: Board
  import_stats: ImportStats
}
