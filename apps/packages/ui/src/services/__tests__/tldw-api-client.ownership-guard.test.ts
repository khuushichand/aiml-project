import { describe, expect, it, vi } from "vitest"

vi.mock("@/services/background-proxy", () => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn(),
  bgStream: vi.fn()
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: vi.fn(async () => null),
    set: vi.fn(async () => undefined),
    remove: vi.fn(async () => undefined)
  }),
  safeStorageSerde: {
    serialize: (value: unknown) => value,
    deserialize: (value: unknown) => value
  }
}))

import { TRANSITIONAL_DOMAIN_OVERLAPS } from "@/services/tldw/client-ownership"
import { TldwApiClientBase } from "@/services/tldw/TldwApiClient"
import {
  adminMethods,
  characterMethods,
  chatRagMethods,
  collectionsMethods,
  mediaMethods,
  modelsAudioMethods,
  presentationsMethods,
  workspaceApiMethods
} from "@/services/tldw/domains"

const domainMethodSources = {
  admin: adminMethods,
  "workspace-api": workspaceApiMethods,
  presentations: presentationsMethods,
  "models-audio": modelsAudioMethods,
  characters: characterMethods,
  collections: collectionsMethods,
  media: mediaMethods,
  "chat-rag": chatRagMethods
} as const

describe("TldwApiClient ownership guard", () => {
  it("matches the recorded transitional overlap inventory", () => {
    const baseMethodNames = new Set(
      Object.getOwnPropertyNames(TldwApiClientBase.prototype).filter(
        (name) => name !== "constructor"
      )
    )

    const actualOverlaps = {
      admin: Object.getOwnPropertyNames(domainMethodSources.admin)
        .filter((name) => baseMethodNames.has(name))
        .sort(),
      "workspace-api": Object.getOwnPropertyNames(domainMethodSources["workspace-api"])
        .filter((name) => baseMethodNames.has(name))
        .sort(),
      presentations: Object.getOwnPropertyNames(domainMethodSources.presentations)
        .filter((name) => baseMethodNames.has(name))
        .sort(),
      "models-audio": Object.getOwnPropertyNames(domainMethodSources["models-audio"])
        .filter((name) => baseMethodNames.has(name))
        .sort(),
      characters: Object.getOwnPropertyNames(domainMethodSources.characters)
        .filter((name) => baseMethodNames.has(name))
        .sort(),
      collections: Object.getOwnPropertyNames(domainMethodSources.collections)
        .filter((name) => baseMethodNames.has(name))
        .sort(),
      media: Object.getOwnPropertyNames(domainMethodSources.media)
        .filter((name) => baseMethodNames.has(name))
        .sort(),
      "chat-rag": Object.getOwnPropertyNames(domainMethodSources["chat-rag"])
        .filter((name) => baseMethodNames.has(name))
        .sort()
    }

    expect(actualOverlaps).toEqual(TRANSITIONAL_DOMAIN_OVERLAPS)
  })
})
