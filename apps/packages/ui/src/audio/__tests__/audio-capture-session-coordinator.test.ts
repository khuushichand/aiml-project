import { describe, expect, it } from "vitest"

import { createAudioCaptureSessionCoordinator } from "@/audio"

describe("audioCaptureSessionCoordinator", () => {
  it("hands off ownership when a second feature claims capture", () => {
    const coordinator = createAudioCaptureSessionCoordinator()
    coordinator.claim("dictation")

    expect(coordinator.claim("live_voice").ownerBeforeClaim).toBe("dictation")
    expect(coordinator.getActiveOwner()).toBe("live_voice")
  })

  it("releases matched ownership", () => {
    const coordinator = createAudioCaptureSessionCoordinator()
    coordinator.claim("dictation")

    const release = coordinator.release("dictation")

    expect(release.ownerBeforeRelease).toBe("dictation")
    expect(release.released).toBe(true)
    expect(coordinator.getActiveOwner()).toBe(null)
  })

  it("keeps a stale owner from clearing a newer capture owner", () => {
    const coordinator = createAudioCaptureSessionCoordinator()
    coordinator.claim("dictation")
    coordinator.claim("live_voice")

    const release = coordinator.release("dictation")

    expect(release.ownerBeforeRelease).toBe("live_voice")
    expect(release.released).toBe(false)
    expect(coordinator.getActiveOwner()).toBe("live_voice")
  })
})
