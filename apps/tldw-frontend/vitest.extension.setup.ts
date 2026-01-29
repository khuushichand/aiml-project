import './vitest.setup'
import { vi } from 'vitest'

if (!window.matchMedia) {
  const matchMediaStub: Window['matchMedia'] = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false
  })
  window.matchMedia = matchMediaStub
}

if (!window.scrollTo) {
  window.scrollTo = vi.fn()
}

if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = vi.fn()
}

class ResizeObserverMock implements ResizeObserver {
  observe(_target: Element, _options?: ResizeObserverOptions) {}
  unobserve(_target: Element) {}
  disconnect() {}
}

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = ResizeObserverMock
}
