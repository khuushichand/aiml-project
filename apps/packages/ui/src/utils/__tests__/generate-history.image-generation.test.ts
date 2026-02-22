import { describe, expect, it } from "vitest"
import { generateHistory } from "@/utils/generate-history"
import {
  IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE,
  IMAGE_GENERATION_USER_MESSAGE_TYPE
} from "@/utils/image-generation-chat"

describe("generateHistory image-generation filtering", () => {
  it("excludes image generation no-op messages from prompt history", () => {
    const history = generateHistory(
      [
        {
          role: "user",
          content: "normal user turn"
        },
        {
          role: "assistant",
          content: "normal assistant turn"
        },
        {
          role: "user",
          content: "image prompt",
          messageType: IMAGE_GENERATION_USER_MESSAGE_TYPE
        },
        {
          role: "assistant",
          content: "",
          messageType: IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE
        }
      ],
      "gpt-4o-mini"
    )

    expect(history).toHaveLength(2)
    expect(history[0]?._getType()).toBe("human")
    expect(history[1]?._getType()).toBe("ai")
  })
})

