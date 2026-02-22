import { createHash } from "node:crypto"
import { describe, expect, it } from "vitest"

import { listEffects } from "../../components/Common/SplashScreen/engine/registry"
import { ASCII_ART_MAP } from "../splash-ascii-art"
import { EXTENDED_SPLASH_CARDS, SOURCE_CANONICAL_SPLASH_CARDS, SPLASH_CARDS } from "../splash-cards"
import { SPLASH_MESSAGES } from "../splash-messages"
import {
  SOURCE_ASCII_ART_KEYS,
  SOURCE_ASCII_ART_SHA256_BY_KEY,
  SOURCE_CANONICAL_CARD_NAME_EFFECT,
  SOURCE_CANONICAL_CARD_NAME_EFFECT_SHA256,
  SOURCE_SPLASH_MESSAGES_COUNT,
  SOURCE_SPLASH_MESSAGES_SHA256,
} from "../splash-source-snapshot"

function sha256(value: unknown): string {
  const payload = JSON.stringify(value)
  return createHash("sha256").update(payload, "utf8").digest("hex")
}

function sha256String(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex")
}

describe("Splash Stage 4 source fidelity", () => {
  it("messages exactly match source count and content hash", () => {
    expect(SPLASH_MESSAGES.length).toBe(SOURCE_SPLASH_MESSAGES_COUNT)
    expect(sha256(SPLASH_MESSAGES)).toBe(SOURCE_SPLASH_MESSAGES_SHA256)
  })

  it("canonical card name/effect mapping matches source snapshot", () => {
    const canonicalNameEffect = SOURCE_CANONICAL_SPLASH_CARDS.map((card) => ({
      name: card.name,
      effect: card.effect,
    }))

    expect(canonicalNameEffect).toEqual(SOURCE_CANONICAL_CARD_NAME_EFFECT)
    expect(sha256(canonicalNameEffect)).toBe(SOURCE_CANONICAL_CARD_NAME_EFFECT_SHA256)
  })

  it("default splash pool is canonical source cards only", () => {
    expect(SPLASH_CARDS).toEqual(SOURCE_CANONICAL_SPLASH_CARDS)

    const sourceNameSet = new Set(SOURCE_CANONICAL_SPLASH_CARDS.map((card) => card.name))
    for (const card of EXTENDED_SPLASH_CARDS) {
      expect(sourceNameSet.has(card.name), `Extended card '${card.name}' must not be in canonical pool`).toBe(false)
    }
  })

  it("canonical cards reference valid effect and ascii keys", () => {
    const effectKeys = new Set(listEffects())
    const asciiKeys = new Set(Object.keys(ASCII_ART_MAP))

    for (const sourceKey of SOURCE_ASCII_ART_KEYS) {
      expect(asciiKeys.has(sourceKey), `Missing source ascii key '${sourceKey}'`).toBe(true)
      const art = ASCII_ART_MAP[sourceKey]
      expect(sha256String(art), `ASCII art payload mismatch for key '${sourceKey}'`).toBe(
        SOURCE_ASCII_ART_SHA256_BY_KEY[sourceKey]
      )
    }

    for (const card of SOURCE_CANONICAL_SPLASH_CARDS) {
      if (card.effect !== null) {
        expect(effectKeys.has(card.effect), `Unknown effect '${card.effect}' on card '${card.name}'`).toBe(true)
      }
      if (card.asciiArt) {
        expect(asciiKeys.has(card.asciiArt), `Unknown ascii art key '${card.asciiArt}' on card '${card.name}'`).toBe(true)
      }
    }
  })
})
