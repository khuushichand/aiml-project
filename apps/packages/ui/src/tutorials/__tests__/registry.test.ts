import { afterEach, describe, expect, it } from "vitest"
import {
  TUTORIAL_REGISTRY,
  getPrimaryTutorialForRoute,
  getTutorialsForRoute,
  normalizeTutorialRoute,
  type TutorialDefinition
} from "../registry"

const injectedTutorials: TutorialDefinition[] = []

afterEach(() => {
  while (injectedTutorials.length > 0) {
    const injected = injectedTutorials.pop()
    if (!injected) continue
    const index = TUTORIAL_REGISTRY.findIndex((tutorial) => tutorial.id === injected.id)
    if (index >= 0) {
      TUTORIAL_REGISTRY.splice(index, 1)
    }
  }
})

describe("tutorial registry route matching", () => {
  it("matches playground tutorials on canonical /chat route", () => {
    const tutorials = getTutorialsForRoute("/chat")

    expect(tutorials.length).toBeGreaterThan(0)
    expect(tutorials.some((tutorial) => tutorial.id === "playground-basics")).toBe(
      true
    )
  })

  it("matches legacy /options/playground alias to /chat tutorials", () => {
    const tutorials = getTutorialsForRoute("/options/playground")

    expect(tutorials.length).toBeGreaterThan(0)
    expect(tutorials.some((tutorial) => tutorial.id === "playground-basics")).toBe(
      true
    )
  })

  it("normalizes extension hash urls for tutorial lookup", () => {
    const tutorials = getTutorialsForRoute(
      "chrome-extension://abc/options.html#/chat?tab=casual"
    )

    expect(tutorials.some((tutorial) => tutorial.id === "playground-basics")).toBe(
      true
    )
  })

  it("supports wildcard route patterns", () => {
    const wildcardTutorial: TutorialDefinition = {
      id: "test-settings-wildcard",
      routePattern: "/settings/*",
      labelKey: "tutorials:test.settings.label",
      labelFallback: "Settings wildcard",
      descriptionKey: "tutorials:test.settings.description",
      descriptionFallback: "Wildcard tutorial",
      steps: [
        {
          target: "body",
          titleKey: "tutorials:test.settings.stepTitle",
          titleFallback: "Step",
          contentKey: "tutorials:test.settings.stepContent",
          contentFallback: "Wildcard match test"
        }
      ]
    }

    TUTORIAL_REGISTRY.push(wildcardTutorial)
    injectedTutorials.push(wildcardTutorial)

    const tutorials = getTutorialsForRoute("/settings/health")
    expect(tutorials.some((tutorial) => tutorial.id === wildcardTutorial.id)).toBe(
      true
    )
  })

  it("returns the basics tutorial as the primary tutorial for /chat", () => {
    const primaryTutorial = getPrimaryTutorialForRoute("/chat")

    expect(primaryTutorial?.id).toBe("playground-basics")
  })

  it("includes basics tutorials for all P0 page routes", () => {
    const expectedBasicsByRoute: Record<string, string> = {
      "/chat": "playground-basics",
      "/workspace-playground": "workspace-playground-basics",
      "/media": "media-basics",
      "/knowledge": "knowledge-basics",
      "/characters": "characters-basics"
    }

    for (const [route, expectedId] of Object.entries(expectedBasicsByRoute)) {
      const tutorials = getTutorialsForRoute(route)
      expect(tutorials.some((tutorial) => tutorial.id === expectedId)).toBe(true)
    }
  })

  it("normalizes legacy paths to canonical routes", () => {
    expect(normalizeTutorialRoute("/options/playground")).toBe("/chat")
    expect(normalizeTutorialRoute("#/workspace-playground?tab=chat")).toBe(
      "/workspace-playground"
    )
    expect(normalizeTutorialRoute("/options/media")).toBe("/media")
    expect(normalizeTutorialRoute("/options/knowledge")).toBe("/knowledge")
    expect(normalizeTutorialRoute("/options/characters")).toBe("/characters")
  })
})
