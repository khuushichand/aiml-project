import { describe, expect, it } from "vitest"

import { CharacterSelect as CommonCharacterSelect } from "../CharacterSelect"
import SidepanelCharacterSelect from "@/components/Sidepanel/Chat/CharacterSelect"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"

describe("CharacterSelect identity integration smoke", () => {
  it("loads the common and sidepanel character selectors and the character compatibility hook", () => {
    expect(CommonCharacterSelect).toBeTypeOf("function")
    expect(SidepanelCharacterSelect).toBeTypeOf("function")
    expect(useSelectedCharacter).toBeTypeOf("function")
  })
})
