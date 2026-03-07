import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const state = vi.hoisted(() => {
  const templates = [
    {
      id: 1,
      title: "Discovery",
      description: "Collect launch context",
      version: 1,
      status: "active" as const,
      steps: [
        {
          id: "goal",
          step_index: 0,
          label: "Goal",
          base_question: "What outcome are we aiming for?",
          question_mode: "stock" as const,
          context_refs: []
        }
      ]
    }
  ]

  return {
    templates,
    createMutateAsync: vi.fn(),
    updateMutateAsync: vi.fn(),
    generateMutateAsync: vi.fn(),
    notification: {
      success: vi.fn(),
      error: vi.fn()
    }
  }
})

vi.mock("@/hooks/useChatWorkflows", () => ({
  useChatWorkflowTemplates: () => ({
    data: state.templates,
    isLoading: false,
    isError: false,
    error: null
  }),
  useCreateChatWorkflowTemplate: () => ({
    mutateAsync: state.createMutateAsync,
    isPending: false
  }),
  useUpdateChatWorkflowTemplate: () => ({
    mutateAsync: state.updateMutateAsync,
    isPending: false
  }),
  useGenerateChatWorkflowDraft: () => ({
    mutateAsync: state.generateMutateAsync,
    isPending: false
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => state.notification
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

import { ChatWorkflowsPage } from "../ChatWorkflowsPage"

describe("ChatWorkflowsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.createMutateAsync.mockResolvedValue({
      id: 2,
      title: "New workflow",
      version: 1,
      status: "active",
      steps: []
    })
    state.updateMutateAsync.mockResolvedValue({
      id: 1,
      title: "Discovery",
      version: 2,
      status: "active",
      steps: []
    })
    state.generateMutateAsync.mockResolvedValue({
      template_draft: {
        title: "Generated workflow",
        description: "Generated from a goal",
        version: 1,
        steps: [
          {
            id: "generated-step",
            step_index: 0,
            label: "Step 1",
            base_question: "What should happen first?",
            question_mode: "stock",
            context_refs: []
          }
        ]
      }
    })
  })

  it("loads a library template into the builder", async () => {
    render(<ChatWorkflowsPage />)

    fireEvent.click(screen.getByRole("button", { name: "Edit in Builder" }))

    await waitFor(() => {
      expect(screen.getByDisplayValue("Discovery")).toBeInTheDocument()
    })
    expect(
      screen.getByDisplayValue("What outcome are we aiming for?")
    ).toBeInTheDocument()
  })

  it("seeds the builder with a generated draft", async () => {
    render(<ChatWorkflowsPage />)

    fireEvent.click(screen.getByRole("tab", { name: "Generate" }))
    fireEvent.change(screen.getByLabelText("Workflow goal"), {
      target: { value: "Launch a customer onboarding flow" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Generate Draft" }))

    await waitFor(() => {
      expect(state.generateMutateAsync).toHaveBeenCalledWith({
        goal: "Launch a customer onboarding flow",
        base_question: "",
        desired_step_count: 4,
        context_refs: []
      })
    })
    expect(screen.getByDisplayValue("Generated workflow")).toBeInTheDocument()
    expect(screen.getByDisplayValue("What should happen first?")).toBeInTheDocument()
  })

  it("creates a new template from the builder draft", async () => {
    render(<ChatWorkflowsPage />)

    fireEvent.click(screen.getByRole("button", { name: "New Template" }))
    fireEvent.change(screen.getByLabelText("Template title"), {
      target: { value: "Intake" }
    })
    fireEvent.change(screen.getByLabelText("Question for step 1"), {
      target: { value: "What are we trying to learn?" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save Template" }))

    await waitFor(() => {
      expect(state.createMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Intake",
          steps: [
            expect.objectContaining({
              step_index: 0,
              base_question: "What are we trying to learn?"
            })
          ]
        })
      )
    })
    expect(state.notification.success).toHaveBeenCalled()
  })
})
