import { readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url))
const SRC_DIR = path.resolve(TEST_DIR, "../../../../")
const SIDEPANEL_BODY_PATH = path.join(
  SRC_DIR,
  "components/Sidepanel/Chat/body.tsx"
)
const PLAYGROUND_CHAT_PATH = path.join(
  SRC_DIR,
  "components/Option/Playground/PlaygroundChat.tsx"
)

const PLAYGROUND_MESSAGE_TAG = /<PlaygroundMessage\b([\s\S]*?)\/>/g
const ATTRIBUTE_PATTERN = /\b([A-Za-z_][A-Za-z0-9_]*)\s*=/g

const OPTION_DEPENDENCY_PROPS = new Set([
  "isTTSEnabled",
  "isStreaming",
  "message_type",
  "messageId",
  "serverMessageId",
  "feedbackQuery",
  "temporaryChat",
  "variants",
  "activeVariantIndex"
])

const collectPlaygroundMessageProps = (source: string): Set<string> => {
  const props = new Set<string>()
  for (const tagMatch of source.matchAll(PLAYGROUND_MESSAGE_TAG)) {
    const attributes = tagMatch[1] || ""
    for (const attrMatch of attributes.matchAll(ATTRIBUTE_PATTERN)) {
      props.add(attrMatch[1])
    }
  }
  return props
}

describe("chat message option parity (extension -> webui)", () => {
  it("keeps all extension sidepanel message option props available in webui playground chat", () => {
    const sidepanelSource = readFileSync(SIDEPANEL_BODY_PATH, "utf8")
    const webuiSource = readFileSync(PLAYGROUND_CHAT_PATH, "utf8")

    const sidepanelProps = collectPlaygroundMessageProps(sidepanelSource)
    const webuiProps = collectPlaygroundMessageProps(webuiSource)

    const sidepanelOptionProps = new Set(
      [...sidepanelProps].filter(
        (prop) => prop.startsWith("on") || OPTION_DEPENDENCY_PROPS.has(prop)
      )
    )

    const missingInWebui = [...sidepanelOptionProps]
      .filter((prop) => !webuiProps.has(prop))
      .sort()

    expect(missingInWebui).toEqual([])
  })
})
