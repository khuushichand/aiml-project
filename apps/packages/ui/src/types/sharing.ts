export type AccessLevel = "view_chat" | "view_chat_add" | "full_edit"
export type ShareResourceType = "workspace" | "chatbook"

export const ACCESS_LEVEL_LABELS: Record<AccessLevel, string> = {
  view_chat: "View only",
  view_chat_add: "View + add sources",
  full_edit: "Full edit"
}

export const ACCESS_LEVEL_COLORS: Record<AccessLevel, string> = {
  view_chat: "default",
  view_chat_add: "blue",
  full_edit: "green"
}

export const getAccessLevelLabel = (accessLevel: string): string =>
  ACCESS_LEVEL_LABELS[accessLevel as AccessLevel] ?? accessLevel

export const getAccessLevelColor = (accessLevel: string): string =>
  ACCESS_LEVEL_COLORS[accessLevel as AccessLevel] ?? "default"

export interface ShareWorkspaceRequest {
  target_user_id: number
  access_level: AccessLevel
  allow_clone?: boolean
}

export interface ShareResponse {
  id: number
  workspace_id: string
  owner_user_id: number
  target_user_id: number
  access_level: AccessLevel
  allow_clone: boolean
  created_at?: string | null
  updated_at?: string | null
}

export type ShareListResponse = ShareResponse[]

export interface SharedWithMeItem {
  share_id: number
  workspace_id: string
  workspace_name: string
  workspace_description?: string | null
  owner_user_id: number
  access_level: AccessLevel
  allow_clone: boolean
  created_at?: string | null
  updated_at?: string | null
}

export type SharedWithMeResponse = SharedWithMeItem[]

export interface CreateTokenRequest {
  resource_type: ShareResourceType
  resource_id: string
  access_level?: AccessLevel
  allow_clone?: boolean
  expires_in_days?: number | null
  password?: string | null
}

export interface TokenResponse {
  id: number
  token: string
  resource_type: ShareResourceType
  resource_id: string
  access_level: AccessLevel
  allow_clone: boolean
  is_password_protected: boolean
  expires_at?: string | null
  created_at?: string | null
}

export type TokenListResponse = TokenResponse[]

export interface PublicSharePreview {
  resource_type: ShareResourceType
  resource_name?: string | null
  resource_description?: string | null
  access_level: AccessLevel
  allow_clone?: boolean
  is_password_protected: boolean
}
