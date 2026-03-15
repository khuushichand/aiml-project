import { describe, expect, it } from "vitest"
import { GitHubProvider } from "../GitHubProvider"

describe("GitHubProvider", () => {
  it("parses owner/repo from github URL", () => {
    const provider = new GitHubProvider()
    const parsed = provider.parseUrl("https://github.com/facebook/react")
    expect(parsed.isValid).toBe(true)
    expect(parsed.owner).toBe("facebook")
    expect(parsed.repo).toBe("react")
  })
})
