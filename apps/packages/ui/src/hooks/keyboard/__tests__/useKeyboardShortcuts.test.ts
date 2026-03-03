import { describe, expect, it, vi } from "vitest"
import {
  executeKeyboardShortcuts,
  type KeyboardShortcutConfig
} from "../useKeyboardShortcuts"

const createKeyboardEvent = (overrides?: Partial<KeyboardEvent>) => {
  return {
    key: "k",
    ctrlKey: false,
    altKey: false,
    shiftKey: false,
    metaKey: false,
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    ...overrides
  } as unknown as KeyboardEvent
}

describe("executeKeyboardShortcuts", () => {
  it("runs matching shortcut action and default prevention", () => {
    const action = vi.fn()
    const shortcuts: KeyboardShortcutConfig[] = [
      {
        shortcut: {
          key: "k",
          ctrlKey: true
        },
        action
      }
    ]

    const event = createKeyboardEvent({ key: "k", ctrlKey: true })
    executeKeyboardShortcuts(event, shortcuts)

    expect(action).toHaveBeenCalledTimes(1)
    expect(event.preventDefault).toHaveBeenCalledTimes(1)
    expect(event.stopPropagation).toHaveBeenCalledTimes(1)
  })

  it("does not run disabled shortcut actions", () => {
    const action = vi.fn()
    const shortcuts: KeyboardShortcutConfig[] = [
      {
        shortcut: { key: "k", ctrlKey: true },
        action,
        enabled: false
      }
    ]

    const event = createKeyboardEvent({ key: "k", ctrlKey: true })
    executeKeyboardShortcuts(event, shortcuts)

    expect(action).not.toHaveBeenCalled()
    expect(event.preventDefault).not.toHaveBeenCalled()
    expect(event.stopPropagation).not.toHaveBeenCalled()
  })

  it("respects preventDefault and stopPropagation flags", () => {
    const action = vi.fn()
    const shortcuts: KeyboardShortcutConfig[] = [
      {
        shortcut: {
          key: "k",
          ctrlKey: true,
          preventDefault: false,
          stopPropagation: false
        },
        action
      }
    ]

    const event = createKeyboardEvent({ key: "k", ctrlKey: true })
    executeKeyboardShortcuts(event, shortcuts)

    expect(action).toHaveBeenCalledTimes(1)
    expect(event.preventDefault).not.toHaveBeenCalled()
    expect(event.stopPropagation).not.toHaveBeenCalled()
  })
})

