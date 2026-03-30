// @vitest-environment jsdom

import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { RecipesTab } from "../RecipesTab"

const validateSpy = vi.fn()
const createSpy = vi.fn()
const setActiveTabSpy = vi.fn()
const setSyntheticReviewRecipeKindSpy = vi.fn()
const recipeManifestState = {
  data: {
    data: [
      {
        recipe_id: "summarization_quality",
        recipe_version: "1",
        name: "Summarization Quality",
        description: "Compare summarization candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["summarization"],
        launchable: true
      },
      {
        recipe_id: "embeddings_model_selection",
        recipe_version: "1",
        name: "Embeddings Model Selection",
        description: "Compare embedding candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["embeddings"],
        launchable: true
      },
      {
        recipe_id: "rag_retrieval_tuning",
        recipe_version: "1",
        name: "RAG Retrieval Tuning",
        description: "Tune retrieval candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["rag", "retrieval"],
        launchable: true,
        capabilities: {
          corpus_sources: ["media_db", "notes"],
          candidate_creation_modes: ["auto_sweep", "manual"],
          graded_relevance_scale: { min: 0, max: 3 }
        },
        default_run_config: {
          candidate_creation_mode: "auto_sweep",
          corpus_scope: { sources: ["media_db", "notes"] },
          weak_supervision_budget: {
            review_sample_fraction: 0.2,
            max_review_samples: 25,
            min_review_samples: 3,
            synthetic_query_limit: 20
          }
        }
      },
      {
        recipe_id: "rag_answer_quality",
        recipe_version: "1",
        name: "RAG Answer Quality",
        description: "Compare answer-generation candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["rag", "generation"],
        launchable: true,
        capabilities: {
          evaluation_modes: ["fixed_context", "live_end_to_end"],
          supervision_modes: ["rubric", "reference_answer", "pairwise", "mixed"],
          candidate_dimensions: [
            "generation_model",
            "prompt_variant",
            "formatting_citation_mode"
          ]
        },
        default_run_config: {
          evaluation_mode: "fixed_context",
          supervision_mode: "rubric"
        }
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

vi.mock("@/store/evaluations", () => ({
  useEvaluationsStore: (selector: (state: any) => unknown) =>
    selector({
      setActiveTab: setActiveTabSpy,
      setSyntheticReviewRecipeKind: setSyntheticReviewRecipeKindSpy
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
        tags: ["summarization"],
        launchable: true
      },
      {
        recipe_id: "embeddings_model_selection",
        recipe_version: "1",
        name: "Embeddings Model Selection",
        description: "Compare embedding candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["embeddings"],
        launchable: true
      },
      {
        recipe_id: "rag_retrieval_tuning",
        recipe_version: "1",
        name: "RAG Retrieval Tuning",
        description: "Tune retrieval candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["rag", "retrieval"],
        launchable: true,
        capabilities: {
          corpus_sources: ["media_db", "notes"],
          candidate_creation_modes: ["auto_sweep", "manual"],
          graded_relevance_scale: { min: 0, max: 3 }
        },
        default_run_config: {
          candidate_creation_mode: "auto_sweep",
          corpus_scope: { sources: ["media_db", "notes"] },
          weak_supervision_budget: {
            review_sample_fraction: 0.2,
            max_review_samples: 25,
            min_review_samples: 3,
            synthetic_query_limit: 20
          }
        }
      },
      {
        recipe_id: "rag_answer_quality",
        recipe_version: "1",
        name: "RAG Answer Quality",
        description: "Compare answer-generation candidates.",
        supported_modes: ["labeled", "unlabeled"],
        tags: ["rag", "generation"],
        launchable: true,
        capabilities: {
          evaluation_modes: ["fixed_context", "live_end_to_end"],
          supervision_modes: ["rubric", "reference_answer", "pairwise", "mixed"],
          candidate_dimensions: [
            "generation_model",
            "prompt_variant",
            "formatting_citation_mode"
          ]
        },
        default_run_config: {
          evaluation_mode: "fixed_context",
          supervision_mode: "rubric"
        }
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

  it("serializes guided rag retrieval tuning inputs into runnable recipe payloads", async () => {
    recipeLaunchReadinessState.data = {
      data: {
        recipe_id: "rag_retrieval_tuning",
        ready: true,
        can_enqueue_runs: true,
        can_reuse_completed_runs: true,
        runtime_checks: {
          recipe_run_worker_enabled: true
        },
        message: null
      }
    }

    render(<RecipesTab />)

    fireEvent.click(screen.getByRole("button", { name: "Use RAG Retrieval Tuning" }))
    fireEvent.change(screen.getByLabelText("Media IDs"), {
      target: { value: "10, 12" }
    })
    fireEvent.change(screen.getByLabelText("Note IDs"), {
      target: { value: "note-7, note-9" }
    })
    fireEvent.click(screen.getByLabelText("Indexing fixed"))
    fireEvent.change(screen.getByLabelText("Candidate creation mode"), {
      target: { value: "manual" }
    })
    fireEvent.change(screen.getByLabelText("Candidate ID 1"), {
      target: { value: "manual-hybrid" }
    })
    fireEvent.change(screen.getByLabelText("Search mode 1"), {
      target: { value: "hybrid" }
    })
    fireEvent.change(screen.getByLabelText("Top K 1"), {
      target: { value: "12" }
    })
    fireEvent.change(screen.getByLabelText("Hybrid alpha 1"), {
      target: { value: "0.6" }
    })
    fireEvent.change(screen.getByLabelText("Reranking strategy 1"), {
      target: { value: "cross_encoder" }
    })
    fireEvent.change(screen.getByLabelText("Chunking preset 1"), {
      target: { value: "compact" }
    })
    fireEvent.change(screen.getByLabelText("Sample ID 1"), {
      target: { value: "q-42" }
    })
    fireEvent.change(screen.getByLabelText("Query text 1"), {
      target: { value: "find the beta architecture note" }
    })
    fireEvent.change(screen.getByLabelText("Relevant media targets 1 (optional)"), {
      target: { value: "10:3\n12:1" }
    })
    fireEvent.change(screen.getByLabelText("Relevant note targets 1 (optional)"), {
      target: { value: "note-7:2" }
    })
    fireEvent.change(screen.getByLabelText("Relevant spans 1 (optional)"), {
      target: { value: "media_db,10,0,42,3\nnotes,note-7,5,25,2" }
    })

    fireEvent.click(screen.getByRole("button", { name: "Run recipe" }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          recipeId: "rag_retrieval_tuning",
          dataset: [
            {
              sample_id: "q-42",
              query: "find the beta architecture note",
              targets: {
                relevant_media_ids: [
                  { id: "10", grade: 3 },
                  { id: "12", grade: 1 }
                ],
                relevant_note_ids: [{ id: "note-7", grade: 2 }],
                relevant_spans: [
                  {
                    source: "media_db",
                    record_id: "10",
                    start: 0,
                    end: 42,
                    grade: 3
                  },
                  {
                    source: "notes",
                    record_id: "note-7",
                    start: 5,
                    end: 25,
                    grade: 2
                  }
                ]
              }
            }
          ],
          runConfig: expect.objectContaining({
            candidate_creation_mode: "manual",
            corpus_scope: {
              sources: ["media_db", "notes"],
              media_ids: [10, 12],
              note_ids: ["note-7", "note-9"],
              indexing_fixed: true
            },
            candidates: [
              expect.objectContaining({
                candidate_id: "manual-hybrid",
                retrieval_config: expect.objectContaining({
                  search_mode: "hybrid",
                  top_k: 12,
                  hybrid_alpha: 0.6,
                  reranking_strategy: "cross_encoder"
                }),
                indexing_config: expect.objectContaining({
                  chunking_preset: "compact"
                })
              })
            ]
          })
        })
      )
    })
  })

  it("serializes guided rag answer quality inputs into runnable recipe payloads", async () => {
    recipeLaunchReadinessState.data = {
      data: {
        recipe_id: "rag_answer_quality",
        ready: true,
        can_enqueue_runs: true,
        can_reuse_completed_runs: true,
        runtime_checks: {
          recipe_run_worker_enabled: true
        },
        message: null
      }
    }

    render(<RecipesTab />)

    fireEvent.click(screen.getByRole("button", { name: "Use RAG Answer Quality" }))
    fireEvent.change(screen.getByLabelText("Context snapshot reference"), {
      target: { value: "ctx-release-2026-03-29" }
    })
    fireEvent.change(screen.getByLabelText("Supervision mode"), {
      target: { value: "mixed" }
    })
    fireEvent.change(screen.getByLabelText("Candidate ID 1"), {
      target: { value: "fixed-best" }
    })
    fireEvent.change(screen.getByLabelText("Generation model 1"), {
      target: { value: "openai:gpt-4.1-mini" }
    })
    fireEvent.change(screen.getByLabelText("Prompt variant 1"), {
      target: { value: "cite-v2" }
    })
    fireEvent.change(screen.getByLabelText("Formatting/citation mode 1"), {
      target: { value: "markdown_citations" }
    })
    fireEvent.change(screen.getByLabelText("Sample ID 1"), {
      target: { value: "sample-42" }
    })
    fireEvent.change(screen.getByLabelText("Query text 1"), {
      target: { value: "What changed in the rollout?" }
    })
    fireEvent.change(screen.getByLabelText("Expected behavior 1"), {
      target: { value: "hedge" }
    })
    fireEvent.change(screen.getByLabelText("Retrieved contexts 1"), {
      target: {
        value: "Doc A :: Rollout completed on Friday.\nDoc B :: Beta remained invite-only."
      }
    })
    fireEvent.change(screen.getByLabelText("Reference answer 1 (optional)"), {
      target: {
        value: "The rollout completed on Friday, while beta access stayed limited."
      }
    })

    fireEvent.click(screen.getByRole("button", { name: "Run recipe" }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          recipeId: "rag_answer_quality",
          dataset: [
            {
              sample_id: "sample-42",
              query: "What changed in the rollout?",
              expected_behavior: "hedge",
              retrieved_contexts: [
                { content: "Doc A :: Rollout completed on Friday." },
                { content: "Doc B :: Beta remained invite-only." }
              ],
              reference_answer:
                "The rollout completed on Friday, while beta access stayed limited."
            }
          ],
          runConfig: expect.objectContaining({
            evaluation_mode: "fixed_context",
            supervision_mode: "mixed",
            context_snapshot_ref: "ctx-release-2026-03-29",
            candidates: [
              {
                candidate_id: "fixed-best",
                generation_model: "openai:gpt-4.1-mini",
                prompt_variant: "cite-v2",
                formatting_citation_mode: "markdown_citations"
              }
            ]
          })
        })
      )
    })
  })

  it("shows guided rag retrieval tuning controls and serializes a normalized launch payload", async () => {
    recipeManifestState.data = {
      data: [
        {
          recipe_id: "rag_retrieval_tuning",
          recipe_version: "1",
          name: "RAG Retrieval Tuning",
          description: "Tune retrieval candidates.",
          supported_modes: ["labeled", "unlabeled"],
          tags: ["rag", "retrieval"],
          launchable: true
        },
        {
          recipe_id: "summarization_quality",
          recipe_version: "1",
          name: "Summarization Quality",
          description: "Compare summarization candidates.",
          supported_modes: ["labeled", "unlabeled"],
          tags: ["summarization"],
          launchable: true
        }
      ]
    }
    recipeLaunchReadinessState.data = {
      data: {
        recipe_id: "rag_retrieval_tuning",
        ready: true,
        can_enqueue_runs: true,
        can_reuse_completed_runs: true,
        runtime_checks: {
          recipe_run_worker_enabled: true
        },
        message: null
      }
    }

    render(<RecipesTab />)

    fireEvent.click(screen.getByRole("button", { name: "Use RAG Retrieval Tuning" }))

    expect(screen.getByText("Corpus sources")).toBeInTheDocument()
    expect(screen.getByText("Weak supervision budget")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Add query sample" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Run recipe" })).toBeEnabled()

    fireEvent.click(screen.getByRole("button", { name: "Run recipe" }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          recipeId: "rag_retrieval_tuning",
          runConfig: expect.objectContaining({
            candidate_creation_mode: "auto_sweep",
            corpus_scope: expect.objectContaining({
              sources: ["media_db", "notes"]
            }),
            weak_supervision_budget: expect.objectContaining({
              review_sample_fraction: 0.2,
              max_review_samples: 25,
              min_review_samples: 3,
              synthetic_query_limit: 20
            })
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

  it("shows a non-launchable recipe notice and disables validate/run", async () => {
    recipeManifestState.data = {
      data: [
        {
          recipe_id: "rag_retrieval_tuning",
          recipe_version: "1",
          name: "RAG Retrieval Tuning",
          description: "Tune retrieval candidates.",
          supported_modes: ["labeled", "unlabeled"],
          tags: ["rag", "retrieval"],
          launchable: false
        },
        {
          recipe_id: "summarization_quality",
          recipe_version: "1",
          name: "Summarization Quality",
          description: "Compare summarization candidates.",
          supported_modes: ["labeled", "unlabeled"],
          tags: ["summarization"],
          launchable: true
        }
      ]
    }
    recipeLaunchReadinessState.data = {
      data: {
        recipe_id: "rag_retrieval_tuning",
        ready: false,
        can_enqueue_runs: false,
        can_reuse_completed_runs: false,
        runtime_checks: {
          recipe_launchable: false,
          recipe_run_worker_enabled: false
        },
        message:
          "Recipe 'rag_retrieval_tuning' is not launchable yet. It is exposed as a stub manifest only."
      }
    }

    render(<RecipesTab />)

    expect(
      screen.getByText(
        "Recipe 'rag_retrieval_tuning' is not launchable yet. It is exposed as a stub manifest only."
      )
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Validate dataset" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Run recipe" })).toBeDisabled()
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

  it("opens the shared synthetic review tab for supported rag recipes", async () => {
    recipeLaunchReadinessState.data = {
      data: {
        recipe_id: "rag_retrieval_tuning",
        ready: true,
        can_enqueue_runs: true,
        can_reuse_completed_runs: true,
        runtime_checks: {
          recipe_run_worker_enabled: true
        },
        message: null
      }
    }

    render(<RecipesTab />)

    fireEvent.click(screen.getByRole("button", { name: "Use RAG Retrieval Tuning" }))
    fireEvent.click(
      screen.getByRole("button", { name: "Review synthetic retrieval drafts" })
    )

    expect(setSyntheticReviewRecipeKindSpy).toHaveBeenCalledWith(
      "rag_retrieval_tuning"
    )
    expect(setActiveTabSpy).toHaveBeenCalledWith("synthetic-review")
  })
})
