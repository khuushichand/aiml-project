import type { WorkspaceState } from '../workspace'

export type WorkspaceSlice<T> = (
  set: (partial: Partial<WorkspaceState> | ((state: WorkspaceState) => Partial<WorkspaceState>)) => void,
  get: () => WorkspaceState
) => T
