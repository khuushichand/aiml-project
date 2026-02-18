import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { CreateTab } from "../CreateTab"
import { useCreateQuestionMutation, useCreateQuizMutation } from "../../hooks"

const interpolate = (template: string, values: Record<string, unknown> | undefined) => {
  return template.replace(/\{\{\s*([^\s}]+)\s*\}\}/g, (_, key: string) => {
    const value = values?.[key]
    return value == null ? "" : String(value)
  })
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            [key: string]: unknown
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      const defaultValue = defaultValueOrOptions?.defaultValue
      if (typeof defaultValue === "string") {
        return interpolate(defaultValue, defaultValueOrOptions)
      }
      return key
    }
  })
}))

vi.mock("../../hooks", () => ({
  useCreateQuizMutation: vi.fn(),
  useCreateQuestionMutation: vi.fn()
}))

describe("CreateTab flexible composition", () => {
  const createQuestionMutateAsync = vi.fn(async () => undefined)

  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()

    if (!(globalThis.crypto as Crypto | undefined)?.randomUUID) {
      Object.defineProperty(globalThis, "crypto", {
        value: {
          randomUUID: () => `question-${Math.random()}`
        },
        configurable: true
      })
    }

    vi.mocked(useCreateQuizMutation).mockReturnValue({
      mutateAsync: vi.fn(async () => ({ id: 42 })),
      isPending: false
    } as any)

    vi.mocked(useCreateQuestionMutation).mockReturnValue({
      mutateAsync: createQuestionMutateAsync,
      isPending: false
    } as any)
  })

  it("supports reordering questions and persists order_index accordingly", async () => {
    render(<CreateTab onNavigateToTake={() => {}} />)

    fireEvent.change(screen.getByPlaceholderText("e.g., Biology Chapter 5"), {
      target: { value: "My Quiz" }
    })

    fireEvent.click(screen.getByRole("button", { name: /Add Your First Question/i }))
    fireEvent.click(screen.getByRole("button", { name: /Add Question/i }))

    const questionInputs = screen.getAllByPlaceholderText("Enter your question...")
    fireEvent.change(questionInputs[0], { target: { value: "First question" } })
    fireEvent.change(questionInputs[1], { target: { value: "Second question" } })

    const option1Inputs = screen.getAllByPlaceholderText("Option 1")
    const option2Inputs = screen.getAllByPlaceholderText("Option 2")
    fireEvent.change(option1Inputs[0], { target: { value: "A1" } })
    fireEvent.change(option2Inputs[0], { target: { value: "A2" } })
    fireEvent.change(option1Inputs[1], { target: { value: "B1" } })
    fireEvent.change(option2Inputs[1], { target: { value: "B2" } })

    fireEvent.click(screen.getByRole("button", { name: "Move question 1 down" }))
    fireEvent.click(screen.getByRole("button", { name: /Save Quiz/i }))

    await waitFor(() => {
      expect(createQuestionMutateAsync).toHaveBeenCalledTimes(2)
    })

    const firstPayload = createQuestionMutateAsync.mock.calls[0][0]
    const secondPayload = createQuestionMutateAsync.mock.calls[1][0]

    expect(firstPayload.question.question_text).toBe("Second question")
    expect(firstPayload.question.order_index).toBe(0)
    expect(secondPayload.question.question_text).toBe("First question")
    expect(secondPayload.question.order_index).toBe(1)
  }, 15000)

  it("enforces multiple-choice option bounds between 2 and 6", () => {
    render(<CreateTab onNavigateToTake={() => {}} />)

    fireEvent.click(screen.getByRole("button", { name: /Add Your First Question/i }))

    const addOptionButton = screen.getByRole("button", { name: /Add Option/i })
    fireEvent.click(addOptionButton)
    fireEvent.click(addOptionButton)

    expect(addOptionButton).toBeDisabled()
    expect(screen.getAllByPlaceholderText(/Option /)).toHaveLength(6)

    for (let i = 0; i < 4; i++) {
      const removableButtons = screen
        .getAllByRole("button", { name: /Remove option/i })
        .filter((button) => !button.hasAttribute("disabled"))
      if (removableButtons.length === 0) {
        break
      }
      fireEvent.click(removableButtons[0])
    }

    expect(screen.getAllByPlaceholderText(/Option /)).toHaveLength(2)
    const removeButtons = screen.getAllByRole("button", { name: /Remove option/i })
    removeButtons.forEach((button) => {
      expect(button).toBeDisabled()
    })
  }, 15000)

  it("remaps selected correct answer when an earlier option is removed", () => {
    render(<CreateTab onNavigateToTake={() => {}} />)

    fireEvent.click(screen.getByRole("button", { name: /Add Your First Question/i }))

    const radios = screen.getAllByRole("radio")
    fireEvent.click(radios[2])
    expect(radios[2]).toBeChecked()

    fireEvent.click(screen.getByRole("button", { name: /Remove option 2 for question 1/i }))

    const radiosAfterRemoval = screen.getAllByRole("radio")
    expect(radiosAfterRemoval).toHaveLength(3)
    expect(radiosAfterRemoval[1]).toBeChecked()
  })
})
