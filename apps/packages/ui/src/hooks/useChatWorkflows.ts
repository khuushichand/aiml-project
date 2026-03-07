import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult
} from "@tanstack/react-query"

import {
  cancelChatWorkflowRun,
  continueChatWorkflowRun,
  createChatWorkflowTemplate,
  deleteChatWorkflowTemplate,
  generateChatWorkflowDraft,
  getChatWorkflowRun,
  getChatWorkflowTemplate,
  getChatWorkflowTranscript,
  listChatWorkflowTemplates,
  startChatWorkflowRun,
  submitChatWorkflowAnswer,
  updateChatWorkflowTemplate
} from "@/services/tldw/chat-workflows"
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
  SubmitChatWorkflowAnswerInput
} from "@/types/chat-workflows"

export const chatWorkflowQueryKeys = {
  all: () => ["chat-workflows"] as const,
  templates: () => [...chatWorkflowQueryKeys.all(), "templates"] as const,
  template: (templateId: number | string) =>
    [...chatWorkflowQueryKeys.templates(), "detail", String(templateId)] as const,
  runs: () => [...chatWorkflowQueryKeys.all(), "runs"] as const,
  run: (runId: string) =>
    [...chatWorkflowQueryKeys.runs(), "detail", String(runId)] as const,
  transcript: (runId: string) =>
    [...chatWorkflowQueryKeys.run(runId), "transcript"] as const
}

export const useChatWorkflowTemplates = (
  options?: { enabled?: boolean }
): UseQueryResult<ChatWorkflowTemplate[], Error> => {
  return useQuery({
    queryKey: chatWorkflowQueryKeys.templates(),
    queryFn: listChatWorkflowTemplates,
    enabled: options?.enabled ?? true
  })
}

export const useChatWorkflowTemplate = (
  templateId: number | null | undefined,
  options?: { enabled?: boolean }
): UseQueryResult<ChatWorkflowTemplate, Error> => {
  return useQuery({
    queryKey: chatWorkflowQueryKeys.template(templateId ?? "unknown"),
    queryFn: () => getChatWorkflowTemplate(Number(templateId)),
    enabled: Boolean(templateId) && (options?.enabled ?? true)
  })
}

export const useCreateChatWorkflowTemplate = (): UseMutationResult<
  ChatWorkflowTemplate,
  Error,
  ChatWorkflowTemplateCreateInput
> => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createChatWorkflowTemplate,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: chatWorkflowQueryKeys.templates()
      })
    }
  })
}

export const useUpdateChatWorkflowTemplate = (
  templateId: number
): UseMutationResult<
  ChatWorkflowTemplate,
  Error,
  ChatWorkflowTemplateUpdateInput
> => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload) => updateChatWorkflowTemplate(templateId, payload),
    onSuccess: async (data) => {
      queryClient.setQueryData(chatWorkflowQueryKeys.template(templateId), data)
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: chatWorkflowQueryKeys.templates()
        }),
        queryClient.invalidateQueries({
          queryKey: chatWorkflowQueryKeys.template(templateId)
        })
      ])
    }
  })
}

export const useDeleteChatWorkflowTemplate = (): UseMutationResult<
  void,
  Error,
  number
> => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteChatWorkflowTemplate,
    onSuccess: async (_data, templateId) => {
      queryClient.removeQueries({
        queryKey: chatWorkflowQueryKeys.template(templateId)
      })
      await queryClient.invalidateQueries({
        queryKey: chatWorkflowQueryKeys.templates()
      })
    }
  })
}

export const useGenerateChatWorkflowDraft = (): UseMutationResult<
  GenerateChatWorkflowDraftResponse,
  Error,
  GenerateChatWorkflowDraftInput
> => {
  return useMutation({
    mutationFn: generateChatWorkflowDraft
  })
}

export const useStartChatWorkflowRun = (): UseMutationResult<
  ChatWorkflowRun,
  Error,
  StartChatWorkflowRunInput
> => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: startChatWorkflowRun,
    onSuccess: (data) => {
      queryClient.setQueryData(chatWorkflowQueryKeys.run(data.run_id), data)
    }
  })
}

export const useChatWorkflowRun = (
  runId: string | null | undefined,
  options?: { enabled?: boolean }
): UseQueryResult<ChatWorkflowRun, Error> => {
  return useQuery({
    queryKey: chatWorkflowQueryKeys.run(runId || "unknown"),
    queryFn: () => getChatWorkflowRun(String(runId)),
    enabled: Boolean(runId) && (options?.enabled ?? true)
  })
}

export const useChatWorkflowTranscript = (
  runId: string | null | undefined,
  options?: { enabled?: boolean }
): UseQueryResult<ChatWorkflowTranscript, Error> => {
  return useQuery({
    queryKey: chatWorkflowQueryKeys.transcript(runId || "unknown"),
    queryFn: () => getChatWorkflowTranscript(String(runId)),
    enabled: Boolean(runId) && (options?.enabled ?? true)
  })
}

export const useSubmitChatWorkflowAnswer = (
  runId: string
): UseMutationResult<ChatWorkflowRun, Error, SubmitChatWorkflowAnswerInput> => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload) => submitChatWorkflowAnswer(runId, payload),
    onSuccess: async (data) => {
      queryClient.setQueryData(chatWorkflowQueryKeys.run(runId), data)
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: chatWorkflowQueryKeys.run(runId)
        }),
        queryClient.invalidateQueries({
          queryKey: chatWorkflowQueryKeys.transcript(runId)
        })
      ])
    }
  })
}

export const useCancelChatWorkflowRun = (
  runId: string
): UseMutationResult<ChatWorkflowRun, Error, void> => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => cancelChatWorkflowRun(runId),
    onSuccess: async (data) => {
      queryClient.setQueryData(chatWorkflowQueryKeys.run(runId), data)
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: chatWorkflowQueryKeys.run(runId)
        }),
        queryClient.invalidateQueries({
          queryKey: chatWorkflowQueryKeys.transcript(runId)
        })
      ])
    }
  })
}

export const useContinueChatWorkflowRun = (
  runId: string
): UseMutationResult<ContinueChatWorkflowResponse, Error, void> => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => continueChatWorkflowRun(runId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: chatWorkflowQueryKeys.run(runId)
      })
    }
  })
}
