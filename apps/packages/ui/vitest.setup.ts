import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

const originalGetComputedStyle = window.getComputedStyle.bind(window)

window.getComputedStyle = ((element: Element, _pseudoElt?: string | null) =>
  originalGetComputedStyle(element)) as typeof window.getComputedStyle

afterEach(() => {
  cleanup()
})
