/**
 * Sharing Types
 * Types for workspace sharing, share tokens, and shared-with-me views
 */

// ─────────────────────────────────────────────────────────────────────────────
// Enums
// ─────────────────────────────────────────────────────────────────────────────

export type ShareScopeType = "team" | "org"
export type AccessLevel = "view_chat" | "view_chat_add" | "full_edit"
export type ShareResourceType = "chatbook" | "workspace"

// ─────────────────────────────────────────────────────────────────────────────
// Workspace Sharing
// ─────────────────────────────────────────────────────────────────────────────

export interface ShareWorkspaceRequest {
  share_scope_type: ShareScopeType
  share_scope_id: number
  access_level: AccessLevel
  allow_clone: boolean
}

export interface ShareResponse {
  id: number
  workspace_id: string
  owner_user_id: number
  share_scope_type: string
  share_scope_id: number
  access_level: string
  allow_clone: boolean
  created_by: number
  created_at?: string
  updated_at?: string
  revoked_at?: string
  is_revoked: boolean
}

export interface ShareListResponse {
  shares: ShareResponse[]
  total: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared With Me
// ─────────────────────────────────────────────────────────────────────────────

export interface SharedWithMeItem {
  share_id: number
  workspace_id: string
  workspace_name?: string
  owner_user_id: number
  owner_username?: string
  access_level: string
  allow_clone: boolean
  shared_at?: string
}

export interface SharedWithMeResponse {
  items: SharedWithMeItem[]
  total: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Share Tokens
// ─────────────────────────────────────────────────────────────────────────────

export interface CreateTokenRequest {
  resource_type: ShareResourceType
  resource_id: string
  access_level: AccessLevel
  allow_clone: boolean
  password?: string
  max_uses?: number
  expires_at?: string
}

export interface TokenResponse {
  id: number
  token_prefix: string
  resource_type: string
  resource_id: string
  access_level: string
  allow_clone: boolean
  is_password_protected: boolean
  max_uses?: number
  use_count: number
  expires_at?: string
  created_at?: string
  revoked_at?: string
  is_revoked: boolean
  raw_token?: string
}

export interface TokenListResponse {
  tokens: TokenResponse[]
  total: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Public Access
// ─────────────────────────────────────────────────────────────────────────────

export interface PublicSharePreview {
  resource_type: string
  resource_name?: string
  resource_description?: string
  is_password_protected: boolean
  access_level: string
}

// ─────────────────────────────────────────────────────────────────────────────
// UI Helpers
// ─────────────────────────────────────────────────────────────────────────────

export const ACCESS_LEVEL_LABELS: Record<AccessLevel, string> = {
  view_chat: "View & Chat",
  view_chat_add: "View, Chat & Add Sources",
  full_edit: "Full Edit",
}

export const ACCESS_LEVEL_COLORS: Record<string, string> = {
  view_chat: "blue",
  view_chat_add: "green",
  full_edit: "orange",
}
