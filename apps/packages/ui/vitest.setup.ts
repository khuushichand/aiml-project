import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

const originalGetComputedStyle = window.getComputedStyle.bind(window)

const TEXTAREA_FALLBACK_STYLE_PROPS = new Set([
  "lineHeight",
  "paddingTop",
  "paddingBottom",
  "borderTopWidth",
  "borderBottomWidth",
  "fontSize",
  "letterSpacing",
  "textIndent"
])

window.getComputedStyle = ((element: Element, _pseudoElt?: string | null) => {
  const computedStyle = originalGetComputedStyle(element)
  if (!(element instanceof HTMLTextAreaElement)) {
    return computedStyle
  }

  return new Proxy(computedStyle, {
    get(target, prop, receiver) {
      const value = Reflect.get(target, prop, receiver)
      if (typeof prop !== "string") {
        return value
      }

      if (prop === "lineHeight" && (value === "" || value === "normal")) {
        return "16px"
      }

      if (
        TEXTAREA_FALLBACK_STYLE_PROPS.has(prop) &&
        (value === "" || value === null || value === undefined || value === "normal")
      ) {
        return "0px"
      }

      return value
    }
  }) as CSSStyleDeclaration
}) as typeof window.getComputedStyle

const IGNORED_TEST_WARNING_PATTERNS = [
  /Could not parse CSS stylesheet/i,
  /invalid value for the .* css style property/i,
  /\[antd: List\].*deprecated/i,
  /\[antd: Notification\].*deprecated/i,
  /\[antd: Collapse\].*expandIconPosition.*deprecated/i,
  /Instance created by `useForm` is not connected to any Form element/i
]

const stringifyConsoleArgs = (args: unknown[]): string =>
  args
    .map((arg) => {
      if (typeof arg === "string") {
        return arg
      }
      if (arg instanceof Error) {
        return `${arg.name}: ${arg.message}`
      }
      try {
        return JSON.stringify(arg)
      } catch {
        return String(arg)
      }
    })
    .join(" ")

const shouldIgnoreTestWarning = (args: unknown[]): boolean => {
  const message = stringifyConsoleArgs(args)
  return IGNORED_TEST_WARNING_PATTERNS.some((pattern) => pattern.test(message))
}

const originalConsoleWarn = console.warn.bind(console)
const originalConsoleError = console.error.bind(console)
const originalStderrWrite = process.stderr.write.bind(process.stderr)

console.warn = (...args: unknown[]) => {
  if (shouldIgnoreTestWarning(args)) {
    return
  }
  originalConsoleWarn(...args)
}

console.error = (...args: unknown[]) => {
  if (shouldIgnoreTestWarning(args)) {
    return
  }
  originalConsoleError(...args)
}

process.stderr.write = ((chunk: unknown, ...rest: unknown[]) => {
  const text =
    typeof chunk === "string"
      ? chunk
      : chunk instanceof Uint8Array
      ? Buffer.from(chunk).toString("utf8")
      : String(chunk)

  if (shouldIgnoreTestWarning([text])) {
    return true
  }

  return (originalStderrWrite as (...args: unknown[]) => boolean)(chunk, ...rest)
}) as typeof process.stderr.write

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
