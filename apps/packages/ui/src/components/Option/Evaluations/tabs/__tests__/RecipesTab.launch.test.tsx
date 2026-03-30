// @vitest-environment jsdom

import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { RecipesTab } from "../RecipesTab"

const validateSpy = vi.fn()
const createSpy = vi.fn()
const recipeManifestState = {
  data: {
    data: [
      {
        recipe_id: "summarization_quality",
        recipe_version: "1",
        name: "Summarization Quality",
        description: "Compare summarization candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["summarization"]
      },
      {
        recipe_id: "embeddings_model_selection",
        recipe_version: "1",
        name: "Embeddings Model Selection",
        description: "Compare embedding candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["embeddings"]
      }
    ]
  },
  isLoading: false,
  isError: false,
  error: null as Error | null
}
const recipeLaunchReadinessState = {
  data: {
    data: {
      recipe_id: "summarization_quality",
      ready: true,
      can_enqueue_runs: true,
      can_reuse_completed_runs: true,
      runtime_checks: {
        recipe_run_worker_enabled: true
      },
      message: null as string | null
    }
  },
  isLoading: false
}
const datasetsState = {
  data: {
    ok: true,
    data: {
      data: [
        {
          id: "dataset-1",
          name: "Saved dataset",
          sample_count: 3,
          created: 0,
          created_by: "user_123"
        }
      ]
    }
  },
  isLoading: false,
  isError: false
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("../../hooks/useRecipes", () => ({
  getRecipeRunUserErrorMessage: (error: unknown) => {
    const rawMessage = error instanceof Error ? error.message : String(error || "")
    if (rawMessage.includes("recipe_run_enqueue_failed")) {
      return "Recipe runs are unavailable because the recipe worker is not running on this server. Enable the evaluations recipe worker and try again."
    }
    return rawMessage || "Failed to start recipe run."
  },
  useRecipeLaunchReadiness: () => recipeLaunchReadinessState,
  useRecipeManifests: () => recipeManifestState,
  useValidateRecipeDataset: () => ({
    mutateAsync: validateSpy,
    isPending: false
  }),
  useCreateRecipeRun: () => ({
    mutateAsync: createSpy,
    isPending: false
  }),
  useRecipeRunReport: (runId: string | null) => ({
    data:
      runId === "recipe-run-1"
        ? {
            data: {
              run: {
                run_id: "recipe-run-1",
                recipe_id: "summarization_quality",
                recipe_version: "1",
                status: "completed",
                created_at: "2026-03-29T12:00:00Z",
                metadata: {
                  recipe_report: {
                    candidates: [
                      {
                        candidate_id: "openai:gpt-4.1-mini",
                        model: "gpt-4.1-mini",
                        provider: "openai",
                        metrics: {
                          quality_score: 0.91,
                          grounding: 0.94,
                          coverage: 0.89,
                          usefulness: 0.86
                        }
                      }
                    ]
                  }
                }
              },
              confidence_summary: {
                confidence: 0.88,
                sample_count: 6
              },
              recommendation_slots: {
                best_overall: {
                  candidate_run_id: "openai:gpt-4.1-mini",
                  reason_code: "highest_quality_score",
                  explanation: "Best grounding and coverage balance."
                },
                best_cheap: {
                  candidate_run_id: null,
                  reason_code: "not_available",
                  explanation: "No cheaper candidate in this run."
                },
                best_local: {
                  candidate_run_id: null,
                  reason_code: "not_available",
                  explanation: "No local candidate in this run."
                }
              }
            }
          }
        : null,
    isLoading: false,
    isError: false
  })
}))

vi.mock("../../hooks/useDatasets", () => ({
  useDatasetsList: () => datasetsState
}))

vi.mock("../../components", () => ({
  JsonEditor: ({
    value,
    onChange
  }: {
    value?: string
    onChange?: (next: string) => void
  }) => (
    <textarea
      data-testid="json-editor"
      value={value || ""}
      onChange={(event) => onChange?.(event.target.value)}
    />
  )
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("RecipesTab recipe launch flow", () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    if (typeof window.matchMedia !== "function") {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn()
        }))
      })
    }
  })

  afterAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia
    })
  })

  beforeEach(() => {
    vi.clearAllMocks()
    recipeManifestState.data = {
      data: [
        {
          recipe_id: "summarization_quality",
          recipe_version: "1",
          name: "Summarization Quality",
          description: "Compare summarization candidates.",
          supported_modes: ["labeled", "unlabeled"],
          tags: ["summarization"]
        },
        {
          recipe_id: "embeddings_model_selection",
          recipe_version: "1",
          name: "Embeddings Model Selection",
          description: "Compare embedding candidates.",
          supported_modes: ["labeled", "unlabeled"],
          tags: ["embeddings"]
        }
      ]
    }
    recipeManifestState.isLoading = false
    recipeManifestState.isError = false
    recipeManifestState.error = null
    recipeLaunchReadinessState.data = {
      data: {
        recipe_id: "summarization_quality",
        ready: true,
        can_enqueue_runs: true,
        can_reuse_completed_runs: true,
        runtime_checks: {
          recipe_run_worker_enabled: true
        },
        message: null
      }
    }
    recipeLaunchReadinessState.isLoading = false
    datasetsState.data = {
      ok: true,
      data: {
        data: [
          {
            id: "dataset-1",
            name: "Saved dataset",
            sample_count: 3,
            created: 0,
            created_by: "user_123"
          }
        ]
      }
    }
    datasetsState.isLoading = false
    datasetsState.isError = false
    validateSpy.mockResolvedValue({
      data: {
        valid: true,
        dataset_mode: "unlabeled",
        sample_count: 2,
        review_sample: {
          required: true,
          sample_size: 2,
          sample_ids: ["sample-0", "sample-1"]
        }
      }
    })
    createSpy.mockResolvedValue({
      data: {
        run_id: "recipe-run-1",
        recipe_id: "summarization_quality",
        status: "completed"
      }
    })
  })

  it("validates, launches, and renders the current recipe report", async () => {
    render(<RecipesTab />)

    expect(screen.getAllByText("Summarization Quality").length).toBeGreaterThan(0)
    expect(screen.getByText("Embeddings Model Selection")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Use Summarization Quality" }))
    fireEvent.click(screen.getByRole("button", { name: "Validate dataset" }))

    await waitFor(() => {
      expect(validateSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          recipeId: "summarization_quality"
        })
      )
    })

    fireEvent.click(screen.getByRole("button", { name: "Run recipe" }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          recipeId: "summarization_quality"
        })
      )
    })

    await waitFor(() => {
      expect(screen.getByText("Current run")).toBeInTheDocument()
      expect(
        screen.getByText("Best grounding and coverage balance.")
      ).toBeInTheDocument()
      expect(screen.getByText("gpt-4.1-mini")).toBeInTheDocument()
    })
  })

  it("serializes guided summarization inputs into dataset and run config payloads", async () => {
    render(<RecipesTab />)

    fireEvent.change(screen.getByLabelText("Source text 1"), {
      target: { value: "Meeting transcript covering alpha and beta decisions." }
    })
    fireEvent.change(screen.getByLabelText("Reference summary 1 (optional)"), {
      target: { value: "Alpha shipped, beta delayed." }
    })
    fireEvent.change(screen.getByLabelText("Candidate models"), {
      target: {
        value: "openai:gpt-4.1-mini\nlocal:mistral-small\nollama:llama3.1:8b"
      }
    })
    fireEvent.change(screen.getByLabelText("Judge provider"), {
      target: { value: "anthropic" }
    })
    fireEvent.change(screen.getByLabelText("Judge model"), {
      target: { value: "claude-3-7-sonnet" }
    })

    fireEvent.click(screen.getByRole("button", { name: "Run recipe" }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          recipeId: "summarization_quality",
          dataset: [
            {
              input: "Meeting transcript covering alpha and beta decisions.",
              expected: "Alpha shipped, beta delayed."
            }
          ],
          runConfig: expect.objectContaining({
            candidate_model_ids: [
              "openai:gpt-4.1-mini",
              "local:mistral-small",
              "ollama:llama3.1:8b"
            ],
            judge_config: expect.objectContaining({
              provider: "anthropic",
              model: "claude-3-7-sonnet"
            })
          })
        })
      )
    })
  })

  it("serializes guided embeddings inputs into runnable retrieval payloads", async () => {
    render(<RecipesTab />)

    fireEvent.click(screen.getByRole("button", { name: "Use Embeddings Model Selection" }))
    fireEvent.change(screen.getByLabelText("Query ID 1"), {
      target: { value: "query-42" }
    })
    fireEvent.change(screen.getByLabelText("Query text 1"), {
      target: { value: "find the beta launch notes" }
    })
    fireEvent.change(screen.getByLabelText("Relevant media IDs 1 (optional)"), {
      target: { value: "7, 9" }
    })
    fireEvent.change(screen.getByLabelText("Comparison mode"), {
      target: { value: "retrieval_stack" }
    })
    fireEvent.change(screen.getByLabelText("Media IDs"), {
      target: { value: "7, 9, 12" }
    })
    fireEvent.change(screen.getByLabelText("Provider 1"), {
      target: { value: "local" }
    })
    fireEvent.change(screen.getByLabelText("Model 1"), {
      target: { value: "bge-large" }
    })

    fireEvent.click(screen.getByRole("button", { name: "Run recipe" }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          recipeId: "embeddings_model_selection",
          dataset: [
            {
              query_id: "query-42",
              input: "find the beta launch notes",
              expected_ids: ["7", "9"]
            }
          ],
          runConfig: expect.objectContaining({
            comparison_mode: "retrieval_stack",
            media_ids: [7, 9, 12],
            candidates: expect.arrayContaining([
              expect.objectContaining({
                provider: "local",
                model: "bge-large"
              })
            ])
          })
        })
      )
    })
  })

  it("keeps raw JSON behind an advanced section while reflecting guided edits", async () => {
    render(<RecipesTab />)

    expect(screen.queryByText("Inline dataset JSON")).not.toBeInTheDocument()
    expect(screen.queryByText("Run config JSON")).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Source text 1"), {
      target: { value: "Guided note source." }
    })
    fireEvent.click(screen.getByText("Advanced JSON"))

    await waitFor(() => {
      expect(screen.getByText("Inline dataset JSON")).toBeInTheDocument()
      expect(
        (screen.getAllByTestId("json-editor")[0] as HTMLTextAreaElement).value
      ).toContain("Guided note source.")
    })
  })

  it("shows the recipe load error details instead of the empty state on fetch failure", () => {
    recipeManifestState.data = undefined as any
    recipeManifestState.isError = true
    recipeManifestState.error = new Error(
      "Add or update your API key in Settings -> tldw server, then try again."
    )

    render(<RecipesTab />)

    expect(screen.getByText("Unable to load recipes")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Add or update your API key in Settings -> tldw server, then try again."
      )
    ).toBeInTheDocument()
    expect(
      screen.queryByText("No recipes are registered yet.")
    ).not.toBeInTheDocument()
  })

  it("maps recipe enqueue failures to recovery guidance", async () => {
    createSpy.mockRejectedValue(new Error("recipe_run_enqueue_failed"))

    render(<RecipesTab />)

    fireEvent.click(screen.getByRole("button", { name: "Use Summarization Quality" }))
    fireEvent.click(screen.getByRole("button", { name: "Run recipe" }))

    await waitFor(() => {
      expect(
        screen.getByText(
          "Recipe runs are unavailable because the recipe worker is not running on this server. Enable the evaluations recipe worker and try again."
        )
      ).toBeInTheDocument()
    })
    expect(screen.queryByText("recipe_run_enqueue_failed")).not.toBeInTheDocument()
  })

  it("warns when new runs cannot be enqueued and limits the force-rerun path", async () => {
    recipeLaunchReadinessState.data = {
      data: {
        recipe_id: "summarization_quality",
        ready: false,
        can_enqueue_runs: false,
        can_reuse_completed_runs: true,
        runtime_checks: {
          recipe_run_worker_enabled: false
        },
        message:
          "New recipe runs are unavailable because the recipe worker is not running on this server."
      }
    }

    render(<RecipesTab />)

    expect(
      screen.getByText(
        "New recipe runs are unavailable because the recipe worker is not running on this server."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "You can still try to reuse a matching completed run with the current config."
      )
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Try matching run" })).toBeEnabled()

    fireEvent.click(
      screen.getByLabelText("Force rerun even if a matching completed run exists")
    )

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Run recipe" })).toBeDisabled()
    })
    expect(
      screen.getByText("Force rerun requires the recipe worker to be available.")
    ).toBeInTheDocument()
  })

  it("keeps validation messaging focused on dataset format and runtime readiness", async () => {
    recipeLaunchReadinessState.data = {
      data: {
        recipe_id: "summarization_quality",
        ready: false,
        can_enqueue_runs: false,
        can_reuse_completed_runs: true,
        runtime_checks: {
          recipe_run_worker_enabled: false
        },
        message:
          "New recipe runs are unavailable because the recipe worker is not running on this server."
      }
    }

    render(<RecipesTab />)

    fireEvent.click(screen.getByRole("button", { name: "Validate dataset" }))

    await waitFor(() => {
      expect(screen.getByText("Dataset format is valid.")).toBeInTheDocument()
    })
    expect(
      screen.getByText("Launch readiness: matching-run reuse only until the worker is enabled.")
    ).toBeInTheDocument()
  })

  it("explains how to create a saved dataset when none are available", () => {
    datasetsState.data = {
      ok: true,
      data: {
        data: []
      }
    }

    render(<RecipesTab />)

    expect(screen.getByRole("button", { name: "Saved dataset" })).toBeDisabled()
    expect(
      screen.getByText("No saved datasets yet. Create one from the Datasets tab or use an inline dataset.")
    ).toBeInTheDocument()
  })
})
