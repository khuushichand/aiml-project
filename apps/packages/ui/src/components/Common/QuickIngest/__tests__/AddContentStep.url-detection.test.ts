import { describe, expect, it } from "vitest"

import { detectTypeFromUrl } from "../AddContentStep"

describe("detectTypeFromUrl", () => {
  it("detects supported media hosts from exact hosts and subdomains", () => {
    expect(detectTypeFromUrl("https://www.youtube.com/watch?v=123")).toBe("video")
    expect(detectTypeFromUrl("https://player.vimeo.com/video/42")).toBe("video")
    expect(detectTypeFromUrl("https://m.soundcloud.com/example/track")).toBe("audio")
    expect(detectTypeFromUrl("https://open.spotify.com/track/abc")).toBe("audio")
  })

  it("does not trust lookalike or suffix-appended hosts", () => {
    expect(detectTypeFromUrl("https://youtube.com.evil.test/watch?v=123")).toBe("web")
    expect(detectTypeFromUrl("https://evil-youtube.com/watch?v=123")).toBe("web")
    expect(detectTypeFromUrl("https://soundcloud.com.evil.test/track")).toBe("web")
  })
})
