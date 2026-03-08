import { describe, expect, it } from "vitest"

import { CharacterSelect as CommonCharacterSelect } from "../CharacterSelect"
import SidepanelCharacterSelect from "@/components/Sidepanel/Chat/CharacterSelect"

describe("CharacterSelect identity integration smoke", () => {
  it("loads the common and sidepanel character selectors", () => {
    expect(CommonCharacterSelect).toBeTypeOf("function")
    expect(SidepanelCharacterSelect).toBeTypeOf("function")
  })
})
