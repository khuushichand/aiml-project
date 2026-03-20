import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("ServerAdminPage audio installer contract", () => {
  it("mounts the shared audio installer with server-scoped framing", () => {
    const source = readFileSync(
      path.resolve(__dirname, "..", "ServerAdminPage.tsx"),
      "utf8"
    )

    expect(source).toContain('import { AudioInstallerPanel } from "@/components/Option/Setup/AudioInstallerPanel"')
    expect(source).toContain('title={t("settings:audioInstaller.adminCardTitle", "Audio installer")}')
    expect(source).toContain("Install and verify server-side STT/TTS bundles for this connected server.")
    expect(source).toContain("<AudioInstallerPanel />")
  })
})
