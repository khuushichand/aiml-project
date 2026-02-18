import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

const originalGetComputedStyle = window.getComputedStyle.bind(window)

window.getComputedStyle = ((element: Element, _pseudoElt?: string | null) =>
  originalGetComputedStyle(element)) as typeof window.getComputedStyle

const evaluateMediaQuery = (query: string): boolean => {
  const width = window.innerWidth || 1024
  const minMatches = [...query.matchAll(/\(min-width:\s*(\d+)px\)/g)]
  const maxMatches = [...query.matchAll(/\(max-width:\s*(\d+)px\)/g)]

  const meetsMin = minMatches.every((match) => width >= Number(match[1]))
  const meetsMax = maxMatches.every((match) => width <= Number(match[1]))

  return meetsMin && meetsMax
}

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: evaluateMediaQuery(query),
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false
  })
})

if (typeof window.ResizeObserver === "undefined") {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  ;(window as any).ResizeObserver = ResizeObserverMock
  ;(globalThis as any).ResizeObserver = ResizeObserverMock
}

afterEach(() => {
  cleanup()
})
