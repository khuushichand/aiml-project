/**
 * Discriminated union for chat scope. Thread through all API calls
 * and history hooks so omitted scope always means "global".
 */
export type ChatScope =
  | { type: "global" }
  | { type: "workspace"; workspaceId: string }

/**
 * Convert a ChatScope into the query/body params expected by the backend.
 * Omitted scope defaults to global.
 */
export const toChatScopeParams = (
  scope?: ChatScope
): { scope_type: "global" } | { scope_type: "workspace"; workspace_id: string } =>
  scope?.type === "workspace"
    ? { scope_type: "workspace", workspace_id: scope.workspaceId }
    : { scope_type: "global" }
