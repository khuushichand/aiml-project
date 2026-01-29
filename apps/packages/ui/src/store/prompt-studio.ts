import { create } from "zustand"

export type StudioSubTab =
  | "projects"
  | "prompts"
  | "testCases"
  | "evaluations"
  | "optimizations"

export type WizardStep =
  | "selectPrompt"
  | "selectTestCases"
  | "configureModel"
  | "review"

type PromptStudioState = {
  // Navigation
  activeSubTab: StudioSubTab
  setActiveSubTab: (tab: StudioSubTab) => void

  // Selection state
  selectedProjectId: number | null
  setSelectedProjectId: (id: number | null) => void

  selectedPromptId: number | null
  setSelectedPromptId: (id: number | null) => void

  selectedEvaluationId: number | null
  setSelectedEvaluationId: (id: number | null) => void

  selectedOptimizationId: number | null
  setSelectedOptimizationId: (id: number | null) => void

  // Multi-select for test cases
  selectedTestCaseIds: number[]
  setSelectedTestCaseIds: (ids: number[]) => void
  toggleTestCaseSelection: (id: number) => void
  clearTestCaseSelection: () => void

  // Wizard state for evaluations/optimizations
  wizardStep: WizardStep
  setWizardStep: (step: WizardStep) => void
  resetWizard: () => void

  // Modal states
  isProjectModalOpen: boolean
  setProjectModalOpen: (open: boolean) => void

  isPromptEditorOpen: boolean
  setPromptEditorOpen: (open: boolean) => void

  isTestCaseModalOpen: boolean
  setTestCaseModalOpen: (open: boolean) => void

  isEvaluationWizardOpen: boolean
  setEvaluationWizardOpen: (open: boolean) => void

  isOptimizationWizardOpen: boolean
  setOptimizationWizardOpen: (open: boolean) => void

  // Edit mode tracking
  editingProjectId: number | null
  setEditingProjectId: (id: number | null) => void

  editingPromptId: number | null
  setEditingPromptId: (id: number | null) => void

  editingTestCaseId: number | null
  setEditingTestCaseId: (id: number | null) => void

  // Reset all state
  resetStore: () => void
}

const initialState = {
  activeSubTab: "projects" as StudioSubTab,
  selectedProjectId: null,
  selectedPromptId: null,
  selectedEvaluationId: null,
  selectedOptimizationId: null,
  selectedTestCaseIds: [] as number[],
  wizardStep: "selectPrompt" as WizardStep,
  isProjectModalOpen: false,
  isPromptEditorOpen: false,
  isTestCaseModalOpen: false,
  isEvaluationWizardOpen: false,
  isOptimizationWizardOpen: false,
  editingProjectId: null,
  editingPromptId: null,
  editingTestCaseId: null
}

export const usePromptStudioStore = create<PromptStudioState>((set) => ({
  ...initialState,

  setActiveSubTab: (activeSubTab) => set({ activeSubTab }),

  setSelectedProjectId: (selectedProjectId) =>
    set({
      selectedProjectId,
      // Reset dependent selections when project changes
      selectedPromptId: null,
      selectedTestCaseIds: [],
      selectedEvaluationId: null,
      selectedOptimizationId: null
    }),

  setSelectedPromptId: (selectedPromptId) => set({ selectedPromptId }),

  setSelectedEvaluationId: (selectedEvaluationId) =>
    set({ selectedEvaluationId }),

  setSelectedOptimizationId: (selectedOptimizationId) =>
    set({ selectedOptimizationId }),

  setSelectedTestCaseIds: (selectedTestCaseIds) =>
    set({ selectedTestCaseIds }),

  toggleTestCaseSelection: (id) =>
    set((state) => ({
      selectedTestCaseIds: state.selectedTestCaseIds.includes(id)
        ? state.selectedTestCaseIds.filter((tcId) => tcId !== id)
        : [...state.selectedTestCaseIds, id]
    })),

  clearTestCaseSelection: () => set({ selectedTestCaseIds: [] }),

  setWizardStep: (wizardStep) => set({ wizardStep }),

  resetWizard: () => set({ wizardStep: "selectPrompt" }),

  setProjectModalOpen: (isProjectModalOpen) => set({ isProjectModalOpen }),

  setPromptEditorOpen: (isPromptEditorOpen) => set({ isPromptEditorOpen }),

  setTestCaseModalOpen: (isTestCaseModalOpen) => set({ isTestCaseModalOpen }),

  setEvaluationWizardOpen: (isEvaluationWizardOpen) =>
    set({ isEvaluationWizardOpen, wizardStep: "selectPrompt" }),

  setOptimizationWizardOpen: (isOptimizationWizardOpen) =>
    set({ isOptimizationWizardOpen, wizardStep: "selectPrompt" }),

  setEditingProjectId: (editingProjectId) => set({ editingProjectId }),

  setEditingPromptId: (editingPromptId) => set({ editingPromptId }),

  setEditingTestCaseId: (editingTestCaseId) => set({ editingTestCaseId }),

  resetStore: () => set(initialState)
}))
