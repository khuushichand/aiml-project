import React from "react"
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  InputNumber,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  Typography
} from "antd"
import {
  ClipboardList,
  CopyPlus,
  PencilLine,
  Plus,
  Sparkles
} from "lucide-react"
import { useTranslation } from "react-i18next"

import { DismissibleBetaAlert } from "@/components/Common/DismissibleBetaAlert"
import { PageShell } from "@/components/Common/PageShell"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import {
  useChatWorkflowTemplates,
  useCreateChatWorkflowTemplate,
  useGenerateChatWorkflowDraft,
  useUpdateChatWorkflowTemplate
} from "@/hooks/useChatWorkflows"
import { useServerOnline } from "@/hooks/useServerOnline"
import type {
  ChatWorkflowTemplate,
  ChatWorkflowTemplateDraft,
  ChatWorkflowTemplateStep
} from "@/types/chat-workflows"

const { Text, Title } = Typography
const { TextArea } = Input

type ChatWorkflowTabKey = "library" | "builder" | "generate"

const createStepId = (): string => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `step-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

const createEmptyStep = (index: number): ChatWorkflowTemplateStep => ({
  id: createStepId(),
  step_index: index,
  label: `Step ${index + 1}`,
  base_question: "",
  question_mode: "stock",
  phrasing_instructions: "",
  context_refs: []
})

const createEmptyDraft = (): ChatWorkflowTemplateDraft => ({
  title: "",
  description: "",
  version: 1,
  steps: [createEmptyStep(0)]
})

const cloneTemplateToDraft = (
  template: Pick<ChatWorkflowTemplate, "title" | "description" | "version" | "steps">
): ChatWorkflowTemplateDraft => ({
  title: template.title,
  description: template.description || "",
  version: template.version,
  steps: template.steps.map((step, index) => ({
    ...step,
    id: step.id || createStepId(),
    step_index: index,
    label: step.label || `Step ${index + 1}`,
    phrasing_instructions: step.phrasing_instructions || "",
    context_refs: Array.isArray(step.context_refs) ? [...step.context_refs] : []
  }))
})

const normalizeDraftForSubmit = (
  draft: ChatWorkflowTemplateDraft
): ChatWorkflowTemplateDraft => ({
  title: draft.title.trim(),
  description: draft.description?.trim() || undefined,
  version: draft.version || 1,
  steps: draft.steps.map((step, index) => ({
    id: step.id.trim() || `step-${index + 1}`,
    step_index: index,
    label: step.label?.trim() || `Step ${index + 1}`,
    base_question: step.base_question.trim(),
    question_mode: step.question_mode,
    phrasing_instructions: step.phrasing_instructions?.trim() || undefined,
    context_refs: Array.isArray(step.context_refs) ? step.context_refs : []
  }))
})

const duplicateDraft = (template: ChatWorkflowTemplate): ChatWorkflowTemplateDraft => {
  const cloned = cloneTemplateToDraft(template)
  return {
    ...cloned,
    title: `${template.title} copy`
  }
}

export const ChatWorkflowsPage: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const notification = useAntdNotification()
  const isOnline = useServerOnline()
  const [activeTab, setActiveTab] = React.useState<ChatWorkflowTabKey>("library")
  const [editingTemplateId, setEditingTemplateId] = React.useState<number | null>(
    null
  )
  const [draft, setDraft] = React.useState<ChatWorkflowTemplateDraft>(() =>
    createEmptyDraft()
  )
  const [generateGoal, setGenerateGoal] = React.useState("")
  const [generateBaseQuestion, setGenerateBaseQuestion] = React.useState("")
  const [desiredStepCount, setDesiredStepCount] = React.useState(4)

  const templatesQuery = useChatWorkflowTemplates()
  const createTemplateMutation = useCreateChatWorkflowTemplate()
  const updateTemplateMutation = useUpdateChatWorkflowTemplate(
    editingTemplateId || 0
  )
  const generateDraftMutation = useGenerateChatWorkflowDraft()

  const openNewTemplate = React.useCallback(() => {
    setEditingTemplateId(null)
    setDraft(createEmptyDraft())
    setActiveTab("builder")
  }, [])

  const openTemplateForEditing = React.useCallback((template: ChatWorkflowTemplate) => {
    setEditingTemplateId(template.id)
    setDraft(cloneTemplateToDraft(template))
    setActiveTab("builder")
  }, [])

  const openTemplateAsCopy = React.useCallback((template: ChatWorkflowTemplate) => {
    setEditingTemplateId(null)
    setDraft(duplicateDraft(template))
    setActiveTab("builder")
  }, [])

  const updateDraftField = React.useCallback(
    (field: "title" | "description", value: string) => {
      setDraft((current) => ({
        ...current,
        [field]: value
      }))
    },
    []
  )

  const updateStep = React.useCallback(
    (
      stepIndex: number,
      field: keyof ChatWorkflowTemplateStep,
      value: ChatWorkflowTemplateStep[keyof ChatWorkflowTemplateStep]
    ) => {
      setDraft((current) => ({
        ...current,
        steps: current.steps.map((step, index) =>
          index === stepIndex
            ? ({
                ...step,
                [field]: value
              } as ChatWorkflowTemplateStep)
            : step
        )
      }))
    },
    []
  )

  const addStep = React.useCallback(() => {
    setDraft((current) => ({
      ...current,
      steps: [...current.steps, createEmptyStep(current.steps.length)]
    }))
  }, [])

  const removeStep = React.useCallback((stepIndex: number) => {
    setDraft((current) => {
      const nextSteps = current.steps.filter((_, index) => index !== stepIndex)
      const normalizedSteps =
        nextSteps.length > 0 ? nextSteps : [createEmptyStep(0)]
      return {
        ...current,
        steps: normalizedSteps.map((step, index) => ({
          ...step,
          step_index: index,
          label: step.label || `Step ${index + 1}`
        }))
      }
    })
  }, [])

  const saveTemplate = React.useCallback(async () => {
    const payload = normalizeDraftForSubmit(draft)
    if (!payload.title) {
      notification.error({
        message: t("common:error", "Error"),
        description: "Template title is required."
      })
      return
    }
    if (payload.steps.some((step) => !step.base_question)) {
      notification.error({
        message: t("common:error", "Error"),
        description: "Each step needs a question before you can save the template."
      })
      return
    }

    try {
      const saved =
        editingTemplateId != null
          ? await updateTemplateMutation.mutateAsync(payload)
          : await createTemplateMutation.mutateAsync(payload)
      setEditingTemplateId(saved.id)
      setDraft(cloneTemplateToDraft(saved))
      notification.success({
        message:
          editingTemplateId != null
            ? "Template updated"
            : "Template created",
        description:
          editingTemplateId != null
            ? "Your workflow changes are saved."
            : "Your workflow is ready for structured Q&A."
      })
      setActiveTab("library")
    } catch (error) {
      notification.error({
        message: t("common:error", "Error"),
        description:
          error instanceof Error
            ? error.message
            : "Unable to save the workflow template."
      })
    }
  }, [
    createTemplateMutation,
    draft,
    editingTemplateId,
    notification,
    t,
    updateTemplateMutation
  ])

  const generateDraft = React.useCallback(async () => {
    try {
      const generated = await generateDraftMutation.mutateAsync({
        goal: generateGoal.trim(),
        base_question: generateBaseQuestion.trim(),
        desired_step_count: desiredStepCount,
        context_refs: []
      })
      setEditingTemplateId(null)
      setDraft(cloneTemplateToDraft(generated.template_draft))
      setActiveTab("builder")
      notification.success({
        message: "Draft generated",
        description: "Review the suggested steps, then save the template."
      })
    } catch (error) {
      notification.error({
        message: t("common:error", "Error"),
        description:
          error instanceof Error
            ? error.message
            : "Unable to generate a workflow draft."
      })
    }
  }, [
    desiredStepCount,
    generateBaseQuestion,
    generateDraftMutation,
    generateGoal,
    notification,
    t
  ])

  const templates = templatesQuery.data || []

  if (!isOnline) {
    return (
      <PageShell className="py-6" maxWidthClassName="max-w-6xl">
        <Empty description="Server is offline. Connect to create or run chat workflows." />
      </PageShell>
    )
  }

  return (
    <PageShell className="py-6" maxWidthClassName="max-w-6xl">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium uppercase tracking-[0.16em] text-text-muted">
            <ClipboardList className="h-3.5 w-3.5" />
            Structured QA
          </div>
          <Title level={2} className="!mb-1">
            Chat Workflows
          </Title>
          <Text className="text-sm text-text-muted">
            Build guided Q&amp;A flows that ask one focused question at a time, preserve the run state,
            and hand off to free chat only when the structure is complete.
          </Text>
        </div>
        <Space wrap>
          <Button icon={<Plus className="h-4 w-4" />} onClick={openNewTemplate}>
            New Template
          </Button>
          <Button
            type="primary"
            icon={<Sparkles className="h-4 w-4" />}
            onClick={() => setActiveTab("generate")}>
            Open Generator
          </Button>
        </Space>
      </div>

      <DismissibleBetaAlert
        storageKey="beta-dismissed:chat-workflows"
        message="Beta feature"
        description="Template authoring is ready. Guided run playback and free-chat handoff land in the next stage."
        className="mb-6"
      />

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as ChatWorkflowTabKey)}
        items={[
          {
            key: "library",
            label: "Library",
            children: (
              <div className="space-y-4">
                <Alert
                  type="info"
                  showIcon
                  title="Reusable templates"
                  description="Keep authored workflows here, then send them into a guided run once the run screen is wired up."
                />
                {templatesQuery.isLoading ? (
                  <div className="flex min-h-[240px] items-center justify-center">
                    <Spin />
                  </div>
                ) : templates.length === 0 ? (
                  <Empty
                    description="No chat workflow templates yet. Start with a blank builder or generate a draft."
                  />
                ) : (
                  <div className="grid gap-4 lg:grid-cols-2">
                    {templates.map((template) => (
                      <Card
                        key={template.id}
                        className="border border-border shadow-sm"
                        title={
                          <div className="flex items-center justify-between gap-3">
                            <span>{template.title}</span>
                            <Tag color={template.status === "active" ? "green" : "default"}>
                              {template.steps.length} steps
                            </Tag>
                          </div>
                        }>
                        <div className="space-y-4">
                          <Text className="block text-sm text-text-muted">
                            {template.description || "No description yet."}
                          </Text>
                          <div className="space-y-2">
                            {template.steps.slice(0, 3).map((step) => (
                              <div
                                key={step.id}
                                className="rounded-lg border border-dashed border-border bg-surface p-3">
                                <Text strong className="block text-xs uppercase text-text-muted">
                                  {step.label || `Step ${step.step_index + 1}`}
                                </Text>
                                <Text className="text-sm">{step.base_question}</Text>
                              </div>
                            ))}
                          </div>
                          <Space wrap>
                            <Button
                              icon={<PencilLine className="h-4 w-4" />}
                              onClick={() => openTemplateForEditing(template)}>
                              Edit in Builder
                            </Button>
                            <Button
                              icon={<CopyPlus className="h-4 w-4" />}
                              onClick={() => openTemplateAsCopy(template)}>
                              Load as Copy
                            </Button>
                          </Space>
                        </div>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )
          },
          {
            key: "builder",
            label: "Builder",
            children: (
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(300px,0.9fr)]">
                <Card
                  title={
                    editingTemplateId != null
                      ? `Editing template #${editingTemplateId}`
                      : "New template"
                  }
                  extra={
                    <Space>
                      <Button onClick={openNewTemplate}>Reset Draft</Button>
                      <Button
                        type="primary"
                        onClick={saveTemplate}
                        loading={
                          createTemplateMutation.isPending ||
                          updateTemplateMutation.isPending
                        }>
                        Save Template
                      </Button>
                    </Space>
                  }>
                  <div className="space-y-5">
                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium">
                          Template title
                        </span>
                        <Input
                          aria-label="Template title"
                          placeholder="Discovery workflow"
                          value={draft.title}
                          onChange={(event) =>
                            updateDraftField("title", event.target.value)
                          }
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium">
                          Template description
                        </span>
                        <Input
                          aria-label="Template description"
                          placeholder="Capture goal, constraints, and success criteria."
                          value={draft.description || ""}
                          onChange={(event) =>
                            updateDraftField("description", event.target.value)
                          }
                        />
                      </label>
                    </div>

                    <div className="space-y-4">
                      {draft.steps.map((step, index) => (
                        <Card
                          key={step.id}
                          size="small"
                          className="border border-border bg-surface"
                          title={
                            <div className="flex items-center gap-2">
                              <span>{step.label || `Step ${index + 1}`}</span>
                              <Tag>{step.question_mode === "stock" ? "Stock" : "LLM phrased"}</Tag>
                            </div>
                          }
                          extra={
                            <Button
                              danger
                              size="small"
                              onClick={() => removeStep(index)}>
                              Remove
                            </Button>
                          }>
                          <div className="space-y-4">
                            <label className="block">
                              <span className="mb-1 block text-sm font-medium">
                                Step label
                              </span>
                              <Input
                                aria-label={`Label for step ${index + 1}`}
                                placeholder={`Step ${index + 1}`}
                                value={step.label || ""}
                                onChange={(event) =>
                                  updateStep(index, "label", event.target.value)
                                }
                              />
                            </label>
                            <label className="block">
                              <span className="mb-1 block text-sm font-medium">
                                {`Question for step ${index + 1}`}
                              </span>
                              <TextArea
                                aria-label={`Question for step ${index + 1}`}
                                autoSize={{ minRows: 2, maxRows: 5 }}
                                placeholder="Ask one concrete question at this step."
                                value={step.base_question}
                                onChange={(event) =>
                                  updateStep(index, "base_question", event.target.value)
                                }
                              />
                            </label>
                            <div className="flex flex-col gap-2 rounded-lg border border-dashed border-border px-4 py-3 md:flex-row md:items-center md:justify-between">
                              <div>
                                <Text strong className="block">
                                  Use LLM phrasing
                                </Text>
                                <Text className="text-sm text-text-muted">
                                  Keep the authored intent, but let the server rephrase the displayed question at run time.
                                </Text>
                              </div>
                              <Switch
                                checked={step.question_mode === "llm_phrased"}
                                onChange={(checked) =>
                                  updateStep(
                                    index,
                                    "question_mode",
                                    checked ? "llm_phrased" : "stock"
                                  )
                                }
                              />
                            </div>
                            {step.question_mode === "llm_phrased" ? (
                              <label className="block">
                                <span className="mb-1 block text-sm font-medium">
                                  Phrasing instructions
                                </span>
                                <TextArea
                                  aria-label={`Phrasing instructions for step ${index + 1}`}
                                  autoSize={{ minRows: 2, maxRows: 4 }}
                                  placeholder="Example: keep it concise and ask for operational detail."
                                  value={step.phrasing_instructions || ""}
                                  onChange={(event) =>
                                    updateStep(
                                      index,
                                      "phrasing_instructions",
                                      event.target.value
                                    )
                                  }
                                />
                              </label>
                            ) : null}
                          </div>
                        </Card>
                      ))}
                    </div>

                    <Button icon={<Plus className="h-4 w-4" />} onClick={addStep}>
                      Add Step
                    </Button>
                  </div>
                </Card>

                <div className="space-y-4">
                  <Card title="Builder notes">
                    <div className="space-y-3 text-sm text-text-muted">
                      <p>
                        Keep each step narrow. If a question could produce two different kinds of answer, split it into two steps.
                      </p>
                      <p>
                        Save deterministic templates here first. The run screen will freeze a snapshot before execution so later edits do not change in-flight sessions.
                      </p>
                    </div>
                  </Card>
                  <Card title="Next stage">
                    <div className="space-y-2 text-sm text-text-muted">
                      <p>
                        After this builder is saved, the next task wires the guided run screen, transcript view, answer submission, and free-chat handoff.
                      </p>
                    </div>
                  </Card>
                </div>
              </div>
            )
          },
          {
            key: "generate",
            label: "Generate",
            children: (
              <Card title="Draft from a goal">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)]">
                  <div className="space-y-4">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium">
                        Workflow goal
                      </span>
                      <Input
                        aria-label="Workflow goal"
                        placeholder="E.g. turn an intake call into a crisp implementation brief"
                        value={generateGoal}
                        onChange={(event) => setGenerateGoal(event.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium">
                        Base question override
                      </span>
                      <Input
                        aria-label="Base question override"
                        placeholder="Optional: What must this workflow learn before it can finish?"
                        value={generateBaseQuestion}
                        onChange={(event) => setGenerateBaseQuestion(event.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium">
                        Desired step count
                      </span>
                      <InputNumber
                        min={1}
                        max={12}
                        value={desiredStepCount}
                        onChange={(value) => setDesiredStepCount(Number(value) || 4)}
                      />
                    </label>
                    <Space>
                      <Button
                        type="primary"
                        icon={<Sparkles className="h-4 w-4" />}
                        onClick={generateDraft}
                        loading={generateDraftMutation.isPending}>
                        Generate Draft
                      </Button>
                    </Space>
                  </div>
                  <div className="rounded-2xl border border-dashed border-border bg-surface p-5">
                    <Text strong className="block">
                      Suggested use
                    </Text>
                    <Text className="mt-2 block text-sm text-text-muted">
                      Start with the outcome you need, not the first question you want to ask. The draft generator is best when it can infer progression from a concrete target.
                    </Text>
                    <Text className="mt-4 block text-sm text-text-muted">
                      Example goals:
                    </Text>
                    <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-text-muted">
                      <li>Prepare an implementation brief for a new feature.</li>
                      <li>Qualify an inbound lead before handing off to sales.</li>
                      <li>Capture a bug report with enough detail to reproduce it.</li>
                    </ul>
                  </div>
                </div>
              </Card>
            )
          }
        ]}
      />
    </PageShell>
  )
}

export default ChatWorkflowsPage
