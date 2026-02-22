import { describe, it, expect } from "vitest"
import { isEditableEventTarget } from "../keyboard-shortcuts"

describe("isEditableEventTarget", () => {
  it("returns true for input-like targets", () => {
    const input = document.createElement("input")
    const textarea = document.createElement("textarea")
    const select = document.createElement("select")

    expect(isEditableEventTarget(input)).toBe(true)
    expect(isEditableEventTarget(textarea)).toBe(true)
    expect(isEditableEventTarget(select)).toBe(true)
  })

  it("returns true for contenteditable regions", () => {
    const editable = document.createElement("div")
    editable.setAttribute("contenteditable", "true")

    const child = document.createElement("span")
    editable.appendChild(child)

    expect(isEditableEventTarget(editable)).toBe(true)
    expect(isEditableEventTarget(child)).toBe(true)
  })

  it("returns true for textbox/combobox roles", () => {
    const textbox = document.createElement("div")
    textbox.setAttribute("role", "textbox")

    const comboboxChild = document.createElement("span")
    const combobox = document.createElement("div")
    combobox.setAttribute("role", "combobox")
    combobox.appendChild(comboboxChild)

    expect(isEditableEventTarget(textbox)).toBe(true)
    expect(isEditableEventTarget(comboboxChild)).toBe(true)
  })

  it("returns false for non-editable targets", () => {
    const regular = document.createElement("div")
    expect(isEditableEventTarget(regular)).toBe(false)
    expect(isEditableEventTarget(null)).toBe(false)
  })
})

