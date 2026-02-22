/**
 * Tutorials Module
 * Exports all tutorial-related types, registry, and helpers
 */

// Types
export type { TutorialStep, TutorialDefinition } from "./registry"

// Registry and helpers
export {
  TUTORIAL_REGISTRY,
  getTutorialsForRoute,
  getTutorialById,
  getPrimaryTutorialForRoute,
  hasTutorialsForRoute,
  getTutorialCountForRoute,
  normalizeTutorialRoute
} from "./registry"

// Tutorial definitions (for direct access if needed)
export { playgroundTutorials } from "./definitions/playground"
export { workspacePlaygroundTutorials } from "./definitions/workspace-playground"
export { mediaTutorials } from "./definitions/media"
export { knowledgeTutorials } from "./definitions/knowledge"
export { charactersTutorials } from "./definitions/characters"
