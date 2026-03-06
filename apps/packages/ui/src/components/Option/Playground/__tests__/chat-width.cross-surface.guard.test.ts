import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readSource = (relativePath: string) =>
  fs.readFileSync(path.resolve(__dirname, relativePath), "utf8")

describe("chat width cross-surface guard", () => {
  it("keeps wider default chat content caps aligned across webui and extension surfaces", () => {
    const playgroundSource = readSource("../Playground.tsx")
    const playgroundChatSource = readSource("../PlaygroundChat.tsx")
    const playgroundFormSource = readSource("../PlaygroundForm.tsx")
    const messageSource = readSource("../../../Common/Playground/Message.tsx")
    const userMessageSource = readSource(
      "../../../Common/Playground/PlaygroundUserMessage.tsx"
    )
    const humanMessageSource = readSource("../../../Common/Playground/HumanMessge.tsx")
    const sidepanelFormSource = readSource("../../../Sidepanel/Chat/form.tsx")
    const sidepanelRouteSource = readSource("../../../../routes/sidepanel-chat.tsx")
    const extensionSidepanelRouteSource = readSource(
      "../../../../../../../tldw-frontend/extension/routes/sidepanel-chat.tsx"
    )

    expect(playgroundSource).toContain("max-w-[64rem]")
    expect(playgroundChatSource).toContain("w-full max-w-5xl md:px-4 mb-4 space-y-2")
    expect(playgroundFormSource).toContain("max-w-[64rem]")
    expect(messageSource).toContain("max-w-5xl")
    expect(messageSource).toContain(
      '"prose break-words text-message dark:prose-invert prose-p:leading-relaxed prose-pre:p-0 dark:prose-dark max-w-none"'
    )
    expect(messageSource).toContain(
      "prose max-w-none dark:prose-invert whitespace-pre-line"
    )
    expect(userMessageSource).toContain("max-w-5xl")
    expect(userMessageSource).toContain(
      "rounded-3xl prose max-w-none dark:prose-invert break-words"
    )
    expect(humanMessageSource).toContain("max-w-none")
    expect(sidepanelFormSource).toContain("max-w-[64rem]")
    expect(sidepanelRouteSource).toContain("w-full max-w-5xl")
    expect(extensionSidepanelRouteSource).toContain("w-full max-w-5xl")
  })
})
