import { describe, expect, it } from "vitest"
import { applyDynamicTextareaSize } from "../useDynamicTextareaSize"

const createTextarea = (
  scrollHeight: number,
  style?: Partial<{ height: string; maxHeight: string; overflowY: string }>
) => ({
  scrollHeight,
  style: {
    height: style?.height ?? "",
    maxHeight: style?.maxHeight ?? "",
    overflowY: style?.overflowY ?? ""
  }
})

describe("applyDynamicTextareaSize", () => {
  it("applies maxHeight and overflow constraints", () => {
    const textarea = createTextarea(220)

    const result = applyDynamicTextareaSize(textarea, 160, null)

    expect(result.heightPx).toBe(160)
    expect(result.changed).toBe(true)
    expect(textarea.style.height).toBe("160px")
    expect(textarea.style.maxHeight).toBe("160px")
    expect(textarea.style.overflowY).toBe("scroll")
  })

  it("skips redundant height writes when height is unchanged", () => {
    const textarea = createTextarea(120, {
      height: "120px",
      maxHeight: "160px",
      overflowY: "hidden"
    })

    const result = applyDynamicTextareaSize(textarea, 160, 120)

    expect(result.heightPx).toBe(120)
    expect(result.changed).toBe(false)
    expect(textarea.style.height).toBe("120px")
    expect(textarea.style.maxHeight).toBe("160px")
    expect(textarea.style.overflowY).toBe("hidden")
  })

  it("clears maxHeight when no max is provided", () => {
    const textarea = createTextarea(90, {
      height: "40px",
      maxHeight: "120px",
      overflowY: "scroll"
    })

    const result = applyDynamicTextareaSize(textarea, undefined, 40)

    expect(result.heightPx).toBe(90)
    expect(result.changed).toBe(true)
    expect(textarea.style.height).toBe("90px")
    expect(textarea.style.maxHeight).toBe("")
    expect(textarea.style.overflowY).toBe("hidden")
  })

  it("resets height before measuring so expanded textareas can shrink", () => {
    const style = {
      height: "220px",
      maxHeight: "",
      overflowY: ""
    }
    const textarea = {
      get scrollHeight() {
        return style.height === "auto" ? 44 : 220
      },
      style
    }

    const result = applyDynamicTextareaSize(
      textarea as any,
      undefined,
      220
    )

    expect(result.heightPx).toBe(44)
    expect(result.changed).toBe(true)
    expect(textarea.style.height).toBe("44px")
  })
})
