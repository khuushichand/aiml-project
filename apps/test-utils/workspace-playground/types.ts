import type { Page } from "@playwright/test"

export type WorkspacePlaygroundPlatform = "web" | "extension"

export interface WorkspacePlaygroundParityContext {
  platform: WorkspacePlaygroundPlatform
  page: Page
  optionsUrl?: string
}
