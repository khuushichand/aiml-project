import { bgRequestClient } from "@/services/background-proxy"
import type {
  ChatWorkflowRun,
  ChatWorkflowTemplate,
  ChatWorkflowTemplateCreateInput,
  ChatWorkflowTemplateUpdateInput,
  ChatWorkflowTranscript,
  ContinueChatWorkflowResponse,
  GenerateChatWorkflowDraftInput,
  GenerateChatWorkflowDraftResponse,
  StartChatWorkflowRunInput,
  SubmitChatWorkflowAnswerInput,
  SubmitChatWorkflowRoundInput
} from "@/types/chat-workflows"

const CHAT_WORKFLOWS_BASE_PATH = "/api/v1/chat-workflows"

const encodePathSegment = (value: string | number): string =>
  encodeURIComponent(String(value))

export const listChatWorkflowTemplates = async (): Promise<
  ChatWorkflowTemplate[]
> => {
  return await bgRequestClient<ChatWorkflowTemplate[]>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/templates`,
    method: "GET"
  })
}

export const getChatWorkflowTemplate = async (
  templateId: number
): Promise<ChatWorkflowTemplate> => {
  return await bgRequestClient<ChatWorkflowTemplate>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/templates/${encodePathSegment(templateId)}`,
    method: "GET"
  })
}

export const createChatWorkflowTemplate = async (
  payload: ChatWorkflowTemplateCreateInput
): Promise<ChatWorkflowTemplate> => {
  return await bgRequestClient<ChatWorkflowTemplate>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/templates`,
    method: "POST",
    body: payload
  })
}

export const updateChatWorkflowTemplate = async (
  templateId: number,
  payload: ChatWorkflowTemplateUpdateInput
): Promise<ChatWorkflowTemplate> => {
  return await bgRequestClient<ChatWorkflowTemplate>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/templates/${encodePathSegment(templateId)}`,
    method: "PUT",
    body: payload
  })
}

export const deleteChatWorkflowTemplate = async (
  templateId: number
): Promise<void> => {
  await bgRequestClient<void>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/templates/${encodePathSegment(templateId)}`,
    method: "DELETE"
  })
}

export const generateChatWorkflowDraft = async (
  payload: GenerateChatWorkflowDraftInput
): Promise<GenerateChatWorkflowDraftResponse> => {
  return await bgRequestClient<GenerateChatWorkflowDraftResponse>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/generate-draft`,
    method: "POST",
    body: payload
  })
}

export const startChatWorkflowRun = async (
  payload: StartChatWorkflowRunInput
): Promise<ChatWorkflowRun> => {
  return await bgRequestClient<ChatWorkflowRun>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/runs`,
    method: "POST",
    body: payload
  })
}

export const getChatWorkflowRun = async (
  runId: string
): Promise<ChatWorkflowRun> => {
  return await bgRequestClient<ChatWorkflowRun>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/runs/${encodePathSegment(runId)}`,
    method: "GET"
  })
}

export const getChatWorkflowTranscript = async (
  runId: string
): Promise<ChatWorkflowTranscript> => {
  return await bgRequestClient<ChatWorkflowTranscript>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/runs/${encodePathSegment(runId)}/transcript`,
    method: "GET"
  })
}

export const submitChatWorkflowAnswer = async (
  runId: string,
  payload: SubmitChatWorkflowAnswerInput
): Promise<ChatWorkflowRun> => {
  return await bgRequestClient<ChatWorkflowRun>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/runs/${encodePathSegment(runId)}/answer`,
    method: "POST",
    body: payload
  })
}

export const respondChatWorkflowRound = async (
  runId: string,
  roundIndex: number,
  payload: SubmitChatWorkflowRoundInput
): Promise<ChatWorkflowRun> => {
  return await bgRequestClient<ChatWorkflowRun>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/runs/${encodePathSegment(runId)}/rounds/${encodePathSegment(roundIndex)}/respond`,
    method: "POST",
    body: payload
  })
}

export const cancelChatWorkflowRun = async (
  runId: string
): Promise<ChatWorkflowRun> => {
  return await bgRequestClient<ChatWorkflowRun>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/runs/${encodePathSegment(runId)}/cancel`,
    method: "POST"
  })
}

export const continueChatWorkflowRun = async (
  runId: string
): Promise<ContinueChatWorkflowResponse> => {
  return await bgRequestClient<ContinueChatWorkflowResponse>({
    path: `${CHAT_WORKFLOWS_BASE_PATH}/runs/${encodePathSegment(runId)}/continue-chat`,
    method: "POST"
  })
}

export type {
  ChatWorkflowRun,
  ChatWorkflowTemplate,
  ChatWorkflowTemplateCreateInput,
  ChatWorkflowTemplateUpdateInput,
  ChatWorkflowTranscript,
  ContinueChatWorkflowResponse,
  GenerateChatWorkflowDraftInput,
  GenerateChatWorkflowDraftResponse,
  StartChatWorkflowRunInput,
  SubmitChatWorkflowAnswerInput,
  SubmitChatWorkflowRoundInput
}
