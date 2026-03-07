export type ChatWorkflowQuestionMode = "stock" | "llm_phrased"

export type ChatWorkflowTemplateStatus = "active" | "archived"

export type ChatWorkflowRunStatus = "active" | "completed" | "canceled"

export type ChatWorkflowContextRef = Record<string, unknown>

export type ChatWorkflowQuestionGenerationMeta = Record<string, unknown>

export type ChatWorkflowTemplateStep = {
  id: string
  step_index: number
  label?: string | null
  base_question: string
  question_mode: ChatWorkflowQuestionMode
  phrasing_instructions?: string | null
  context_refs: ChatWorkflowContextRef[]
}

export type ChatWorkflowTemplateDraft = {
  title: string
  description?: string | null
  version?: number
  steps: ChatWorkflowTemplateStep[]
}

export type ChatWorkflowTemplate = ChatWorkflowTemplateDraft & {
  id: number
  version: number
  status: ChatWorkflowTemplateStatus
  created_at?: string | null
  updated_at?: string | null
}

export type ChatWorkflowTemplateCreateInput = ChatWorkflowTemplateDraft

export type ChatWorkflowTemplateUpdateInput = {
  title?: string
  description?: string | null
  steps?: ChatWorkflowTemplateStep[]
  status?: ChatWorkflowTemplateStatus
}

export type GenerateChatWorkflowDraftInput = {
  goal: string
  base_question?: string | null
  desired_step_count?: number
  context_refs?: ChatWorkflowContextRef[]
}

export type GenerateChatWorkflowDraftResponse = {
  template_draft: ChatWorkflowTemplateDraft
}

export type StartChatWorkflowRunInput = {
  template_id?: number
  template_draft?: ChatWorkflowTemplateDraft
  selected_context_refs: ChatWorkflowContextRef[]
  question_renderer_model?: string | null
}

export type SubmitChatWorkflowAnswerInput = {
  step_index: number
  answer_text: string
  idempotency_key?: string | null
}

export type ContinueChatWorkflowResponse = {
  conversation_id: string
}

export type ChatWorkflowAnswer = {
  step_id: string
  step_index: number
  displayed_question: string
  answer_text: string
  question_generation_meta: ChatWorkflowQuestionGenerationMeta
  answered_at?: string | null
}

export type ChatWorkflowRun = {
  run_id: string
  template_id?: number | null
  template_version: number
  status: ChatWorkflowRunStatus
  current_step_index: number
  started_at?: string | null
  completed_at?: string | null
  canceled_at?: string | null
  free_chat_conversation_id?: string | null
  selected_context_refs: ChatWorkflowContextRef[]
  current_question?: string | null
  answers: ChatWorkflowAnswer[]
}

export type ChatWorkflowTranscriptMessage = {
  role: "assistant" | "user" | string
  content: string
  step_index?: number
}

export type ChatWorkflowTranscript = {
  run_id: string
  messages: ChatWorkflowTranscriptMessage[]
}
