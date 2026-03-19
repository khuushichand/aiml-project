import React from "react";
import type { NotificationInstance } from "antd/es/notification/interface";
import type { TFunction } from "i18next";
import {
  generateID,
  updateMessage,
} from "@/db/dexie/helpers";
import type { ChatDocuments } from "@/models/ChatTypes";
import { normalChatMode } from "@/hooks/chat-modes/normalChatMode";
import { continueChatMode } from "@/hooks/chat-modes/continueChatMode";
import { ragMode } from "@/hooks/chat-modes/ragMode";
import { tabChatMode } from "@/hooks/chat-modes/tabChatMode";
import { documentChatMode } from "@/hooks/chat-modes/documentChatMode";
import {
  validateBeforeSubmit,
  createSaveMessageOnSuccess,
  createSaveMessageOnError,
} from "@/hooks/utils/messageHelpers";
import { type UploadedFile } from "@/db/dexie/types";
import { resolveImageBackendCandidates } from "@/utils/image-backends";
import {
  PLAYGROUND_IMAGE_EVENT_SYNC_DEFAULT_STORAGE_KEY,
  type ImageGenerationEventSyncPolicy,
  type ImageGenerationEventSyncMode,
  type ImageGenerationRefineMetadata,
  type ImageGenerationPromptMode,
  type ImageGenerationRequestSnapshot,
} from "@/utils/image-generation-chat";
import { updatePageTitle } from "@/utils/update-page-title";
import {
  DEFAULT_MESSAGE_STEERING_PROMPTS,
  hasActiveMessageSteering,
  normalizeMessageSteeringPrompts,
  resolveMessageSteering,
} from "@/utils/message-steering";
import {
  SELECTED_CHARACTER_STORAGE_KEY,
  selectedCharacterStorage,
  selectedCharacterSyncStorage,
  parseSelectedCharacterValue,
} from "@/utils/selected-character-storage";
import {
  tldwClient,
  type ConversationState,
} from "@/services/tldw/TldwApiClient";
import { generateTitle } from "@/services/title";
import { MAX_COMPARE_MODELS } from "@/hooks/chat/compare-constants";
import { useChatSettingsRecord } from "@/hooks/chat/useChatSettingsRecord";
import { ensurePersonaServerChat } from "@/hooks/chat/personaServerChat";
import {
  isPersonaAssistantSelection,
  type AssistantSelection,
} from "@/types/assistant-selection";
import type { Character } from "@/types/character";
import type { ChatScope } from "@/types/chat-scope";
import type {
  MessageSteeringMode,
  MessageSteeringPromptTemplates,
  MessageSteeringState,
} from "@/types/message-steering";
import {
  type ChatHistory,
  type Message,
  useStoreMessageOption,
  type Knowledge,
  type ReplyTarget,
  type ToolChoice,
} from "@/store/option";
import type { ChatModelSettings } from "@/store/model";
import type { SaveMessageData } from "@/types/chat-modes";
import { updateActiveVariant } from "@/utils/message-variants";
import { saveHistory, saveMessage } from "@/db/dexie/helpers";
import { useStorage } from "@plasmohq/storage/hook";
import {
  PLAYGROUND_APPEND_FORMATTING_GUIDE_PROMPT_STORAGE_KEY,
  resolveOutputFormattingGuideSuffix,
} from "@/utils/output-formatting-guide";

// Sub-modules
import {
  type ChatModeOverrides,
  type SaveMessagePayload,
  buildHistoryFromMessagesFactory,
  buildHistoryForModel,
} from "./chat-action-utils";
import { useImageEventSync } from "./useImageEventSync";
import { useMessageOperations } from "./useMessageOperations";
import { createCharacterChatMode } from "./useCharacterChatMode";
import { useCompareSubmit } from "./useCompareSubmit";

// Re-export types for backward compat
export type { ChatModeOverrides, SaveMessagePayload } from "./chat-action-utils";

const loadActorSettings = () => import("@/services/actor-settings");

import type { ChatModelSettingsStore } from "./chat-action-utils";

type UseChatActionsOptions = {
  t: TFunction;
  notification: NotificationInstance;
  abortController: AbortController | null;
  setAbortController: (controller: AbortController | null) => void;
  messages: Message[];
  setMessages: (
    messagesOrUpdater: Message[] | ((prev: Message[]) => Message[]),
  ) => void;
  history: ChatHistory;
  setHistory: (
    historyOrUpdater: ChatHistory | ((prev: ChatHistory) => ChatHistory),
  ) => void;
  historyId: string | null;
  setHistoryId: (
    historyId: string | null,
    options?: { preserveServerChatId?: boolean },
  ) => void;
  temporaryChat: boolean;
  selectedModel: string | null;
  useOCR: boolean;
  selectedSystemPrompt: string | null;
  selectedKnowledge: Knowledge | null;
  toolChoice: ToolChoice;
  webSearch: boolean;
  currentChatModelSettings: ChatModelSettingsStore;
  setIsSearchingInternet: (isSearchingInternet: boolean) => void;
  setIsProcessing: (isProcessing: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setActionInfo: (actionInfo: string) => void;
  fileRetrievalEnabled: boolean;
  ragMediaIds: number[] | null;
  ragSearchMode: "hybrid" | "vector" | "fts";
  ragTopK: number | null;
  ragEnableGeneration: boolean;
  ragEnableCitations: boolean;
  ragSources: string[];
  ragAdvancedOptions: Record<string, unknown>;
  serverChatId: string | null;
  serverChatTitle: string | null;
  serverChatCharacterId: string | number | null;
  serverChatAssistantKind: "character" | "persona" | null;
  serverChatAssistantId: string | null;
  serverChatPersonaMemoryMode: "read_only" | "read_write" | null;
  serverChatState: ConversationState | null;
  serverChatTopic: string | null;
  serverChatClusterId: string | null;
  serverChatSource: string | null;
  serverChatExternalRef: string | null;
  setServerChatId: (id: string | null) => void;
  setServerChatTitle: (title: string | null) => void;
  setServerChatCharacterId: (id: string | number | null) => void;
  setServerChatAssistantKind: (kind: "character" | "persona" | null) => void;
  setServerChatAssistantId: (id: string | null) => void;
  setServerChatPersonaMemoryMode: (
    mode: "read_only" | "read_write" | null,
  ) => void;
  setServerChatMetaLoaded: (loaded: boolean) => void;
  setServerChatState: (state: ConversationState | null) => void;
  setServerChatVersion: (version: number | null) => void;
  setServerChatTopic: (topic: string | null) => void;
  setServerChatClusterId: (clusterId: string | null) => void;
  setServerChatSource: (source: string | null) => void;
  setServerChatExternalRef: (ref: string | null) => void;
  ensureServerChatHistoryId: (
    chatId: string,
    title?: string,
  ) => Promise<string | null>;
  contextFiles: UploadedFile[];
  setContextFiles: (files: UploadedFile[]) => void;
  documentContext: ChatDocuments | null;
  setDocumentContext: (docs: ChatDocuments) => void;
  uploadedFiles: UploadedFile[];
  compareModeActive: boolean;
  compareSelectedModels: string[];
  compareMaxModels: number;
  compareFeatureEnabled: boolean;
  markCompareHistoryCreated: (historyId: string) => void;
  replyTarget: ReplyTarget | null;
  clearReplyTarget: () => void;
  messageSteeringPrompts: MessageSteeringPromptTemplates | null;
  setSelectedQuickPrompt: (prompt: string | null) => void;
  setSelectedSystemPrompt: (prompt: string) => void;
  invalidateServerChatHistory: () => void;
  selectedCharacter: Character | null;
  selectedAssistant: AssistantSelection | null;
  messageSteeringMode: MessageSteeringMode;
  messageSteeringForceNarrate: boolean;
  clearMessageSteering: () => void;
  scope?: ChatScope;
};

export const useChatActions = ({
  t,
  notification,
  abortController,
  setAbortController,
  messages,
  setMessages,
  history,
  setHistory,
  historyId,
  setHistoryId,
  temporaryChat,
  selectedModel,
  useOCR,
  selectedSystemPrompt,
  selectedKnowledge,
  toolChoice,
  webSearch,
  currentChatModelSettings,
  setIsSearchingInternet,
  setIsProcessing,
  setStreaming,
  setActionInfo,
  fileRetrievalEnabled,
  ragMediaIds,
  ragSearchMode,
  ragTopK,
  ragEnableGeneration,
  ragEnableCitations,
  ragSources,
  ragAdvancedOptions,
  serverChatId,
  serverChatTitle,
  serverChatCharacterId,
  serverChatAssistantKind,
  serverChatAssistantId,
  serverChatPersonaMemoryMode,
  serverChatState,
  serverChatTopic,
  serverChatClusterId,
  serverChatSource,
  serverChatExternalRef,
  setServerChatId,
  setServerChatTitle,
  setServerChatCharacterId,
  setServerChatAssistantKind,
  setServerChatAssistantId,
  setServerChatPersonaMemoryMode,
  setServerChatMetaLoaded,
  setServerChatState,
  setServerChatVersion,
  setServerChatTopic,
  setServerChatClusterId,
  setServerChatSource,
  setServerChatExternalRef,
  ensureServerChatHistoryId,
  contextFiles,
  setContextFiles,
  documentContext,
  setDocumentContext,
  uploadedFiles,
  compareModeActive,
  compareSelectedModels,
  compareMaxModels,
  compareFeatureEnabled,
  markCompareHistoryCreated,
  replyTarget,
  clearReplyTarget,
  messageSteeringPrompts,
  setSelectedQuickPrompt,
  setSelectedSystemPrompt,
  invalidateServerChatHistory,
  selectedCharacter,
  selectedAssistant,
  messageSteeringMode,
  messageSteeringForceNarrate,
  clearMessageSteering,
  scope,
}: UseChatActionsOptions) => {
  const sendInFlightRef = React.useRef(false);
  const discardCurrentTurnOnAbortRef = React.useRef(false);
  const messagesRef = React.useRef(messages);
  React.useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const [appendFormattingGuidePrompt] = useStorage(
    PLAYGROUND_APPEND_FORMATTING_GUIDE_PROMPT_STORAGE_KEY,
    false,
  );
  const [imageEventSyncGlobalDefault] =
    useStorage<ImageGenerationEventSyncMode>(
      PLAYGROUND_IMAGE_EVENT_SYNC_DEFAULT_STORAGE_KEY,
      "off",
    );

  // --- Model resolution ---
  const normalizeSelectedModel = React.useCallback(
    (value: string | null | undefined): string | null => {
      if (typeof value !== "string") return null;
      const trimmed = value.trim();
      return trimmed.length > 0 ? trimmed : null;
    },
    [],
  );

  const getEffectiveSelectedModel = React.useCallback(
    (preferred?: string | null): string | null => {
      const fromPreferred = normalizeSelectedModel(preferred);
      if (fromPreferred) return fromPreferred;
      const fromHookState = normalizeSelectedModel(selectedModel);
      if (fromHookState) return fromHookState;
      try {
        const fromStore = normalizeSelectedModel(
          useStoreMessageOption.getState().selectedModel,
        );
        if (fromStore) return fromStore;
      } catch {
        // Best-effort fallback only.
      }
      return null;
    },
    [normalizeSelectedModel, selectedModel],
  );

  // --- Chat settings ---
  const { settings: chatSettings } = useChatSettingsRecord({
    historyId,
    serverChatId,
  });
  const greetingEnabled = chatSettings?.greetingEnabled ?? true;
  const greetingSelectionId =
    typeof chatSettings?.greetingSelectionId === "string"
      ? chatSettings.greetingSelectionId
      : null;
  const greetingsChecksum =
    typeof chatSettings?.greetingsChecksum === "string"
      ? chatSettings.greetingsChecksum
      : null;
  const useCharacterDefault = Boolean(chatSettings?.useCharacterDefault);
  const directedCharacterId = React.useMemo(() => {
    const raw = chatSettings?.directedCharacterId;
    const parsed = Number.parseInt(String(raw ?? ""), 10);
    if (!Number.isFinite(parsed) || parsed <= 0) return null;
    return parsed;
  }, [chatSettings?.directedCharacterId]);

  // --- Message steering ---
  const resolvedMessageSteering = React.useMemo(
    () =>
      resolveMessageSteering({
        mode: messageSteeringMode,
        forceNarrate: messageSteeringForceNarrate,
      }),
    [messageSteeringForceNarrate, messageSteeringMode],
  );
  const resolvedMessageSteeringPrompts = React.useMemo(
    () =>
      normalizeMessageSteeringPrompts(
        messageSteeringPrompts ?? DEFAULT_MESSAGE_STEERING_PROMPTS,
      ),
    [messageSteeringPrompts],
  );
  const systemPromptAppendix = React.useMemo(
    () =>
      resolveOutputFormattingGuideSuffix(Boolean(appendFormattingGuidePrompt)),
    [appendFormattingGuidePrompt],
  );

  // --- Image event sync ---
  const { resolveImageEventSyncModeForPayload, updateImageEventSyncMetadata } =
    useImageEventSync({
      chatSettings,
      imageEventSyncGlobalDefault,
      setMessages,
    });

  // --- Character resolution ---
  const resolveSelectedCharacter = React.useCallback(async () => {
    try {
      const storedRaw = await selectedCharacterStorage.get(
        SELECTED_CHARACTER_STORAGE_KEY,
      );
      const stored = parseSelectedCharacterValue<Character>(storedRaw);
      if (stored?.id) {
        if (
          !selectedCharacter?.id ||
          String(stored.id) !== String(selectedCharacter.id)
        ) {
          return stored;
        }
      }
      const storedSyncRaw = await selectedCharacterSyncStorage.get(
        SELECTED_CHARACTER_STORAGE_KEY,
      );
      const storedSync = parseSelectedCharacterValue<Character>(storedSyncRaw);
      if (storedSync?.id) {
        await selectedCharacterStorage
          .set(SELECTED_CHARACTER_STORAGE_KEY, storedSync)
          .catch(() => {});
        if (
          !selectedCharacter?.id ||
          String(storedSync.id) !== String(selectedCharacter.id)
        ) {
          return storedSync;
        }
      }
    } catch {
      // best-effort only
    }
    return selectedCharacter;
  }, [selectedCharacter]);

  // --- Save helpers ---
  const baseSaveMessageOnSuccess = createSaveMessageOnSuccess(
    temporaryChat,
    setHistoryId as (
      id: string,
      options?: { preserveServerChatId?: boolean },
    ) => void,
  );
  const saveMessageOnError = createSaveMessageOnError(
    temporaryChat,
    history,
    setHistory,
    setHistoryId as (
      id: string,
      options?: { preserveServerChatId?: boolean },
    ) => void,
  );

  const saveMessageOnSuccess = async (
    payload?: SaveMessagePayload,
  ): Promise<string | null> => {
    const payloadWithHistory = payload
      ? {
          ...payload,
          setHistoryId:
            payload.setHistoryId ??
            ((id: string) => {
              setHistoryId(id);
            }),
        }
      : undefined;
    const historyKey = await baseSaveMessageOnSuccess(payloadWithHistory);

    if (!payload?.historyId && historyKey) {
      markCompareHistoryCreated(historyKey);
    }

    if (temporaryChat) {
      return historyKey;
    }

    let skipServerWrite = false;
    const payloadConversationId =
      typeof payload?.conversationId === "string"
        ? payload.conversationId
        : payload?.conversationId != null
          ? String(payload.conversationId)
          : null;
    const effectiveChatId = payloadConversationId || serverChatId;
    if (!effectiveChatId) return historyKey;

    const syncMode = resolveImageEventSyncModeForPayload(payload);
    if (syncMode !== "off" && payload) {
      try {
        await tldwClient.initialize().catch(() => null);
        const { buildImageGenerationEventMirrorContent } = await import(
          "@/utils/image-generation-chat"
        );
        const mirrorContent = buildImageGenerationEventMirrorContent(payload as any);
        if (mirrorContent) {
          const result = (await tldwClient.addChatMessage(
            effectiveChatId,
            {
              role: "assistant",
              content: mirrorContent,
            },
            scope ? { scope } : undefined,
          )) as { id?: string | number } | null;
          await updateImageEventSyncMetadata(payload, {
            status: "synced",
            policy: payload.imageEventSyncPolicy ?? "inherit",
            mode: syncMode,
            serverMessageId:
              result?.id != null ? String(result.id) : undefined,
          });
        }
      } catch (syncErr) {
        console.warn("[saveMessageOnSuccess] image-event-sync failed:", syncErr);
        if (payload) {
          await updateImageEventSyncMetadata(payload, {
            status: "failed",
            policy: payload.imageEventSyncPolicy ?? "inherit",
            mode: syncMode,
            error: syncErr instanceof Error ? syncErr.message : String(syncErr),
          });
        }
      }
    }

    return historyKey;
  };

  // --- Persona server chat ---
  const ensurePersonaServerChatWithState = React.useCallback(
    async ({
      assistant,
      serverChatIdOverride,
    }: {
      assistant: AssistantSelection & { kind: "persona" };
      serverChatIdOverride?: string | null;
    }) =>
      ensurePersonaServerChat({
        assistant,
        serverChatIdOverride,
        serverChatId,
        serverChatTitle,
        serverChatAssistantKind,
        serverChatAssistantId,
        serverChatPersonaMemoryMode,
        serverChatState,
        serverChatTopic,
        serverChatClusterId,
        serverChatSource,
        serverChatExternalRef,
        historyId,
        temporaryChat,
        scope,
        createChat: (payload, createOptions) =>
          tldwClient.createChat(payload, createOptions),
        ensureServerChatHistoryId,
        invalidateServerChatHistory,
        setServerChatId,
        setServerChatTitle,
        setServerChatCharacterId,
        setServerChatAssistantKind,
        setServerChatAssistantId,
        setServerChatPersonaMemoryMode,
        setServerChatMetaLoaded,
        setServerChatState,
        setServerChatVersion,
        setServerChatTopic,
        setServerChatClusterId,
        setServerChatSource,
        setServerChatExternalRef,
      }),
    [
      ensureServerChatHistoryId,
      historyId,
      invalidateServerChatHistory,
      serverChatAssistantId,
      serverChatAssistantKind,
      serverChatClusterId,
      serverChatExternalRef,
      serverChatId,
      serverChatPersonaMemoryMode,
      serverChatSource,
      serverChatState,
      serverChatTitle,
      serverChatTopic,
      scope,
      setServerChatAssistantId,
      setServerChatAssistantKind,
      setServerChatCharacterId,
      setServerChatClusterId,
      setServerChatExternalRef,
      setServerChatId,
      setServerChatMetaLoaded,
      setServerChatPersonaMemoryMode,
      setServerChatSource,
      setServerChatState,
      setServerChatTitle,
      setServerChatTopic,
      setServerChatVersion,
      temporaryChat,
    ],
  );

  // --- History builders ---
  const buildHistoryFromMessages = React.useCallback(
    buildHistoryFromMessagesFactory(greetingEnabled),
    [greetingEnabled],
  );

  const refreshHistoryFromMessages = React.useCallback(() => {
    const next = buildHistoryFromMessages(messagesRef.current);
    setHistory(next);
  }, [buildHistoryFromMessages, setHistory]);

  const extractContinuationDraft = React.useCallback(
    (fullText: string, priorText: string): string => {
      const trimmedFull = fullText.trim();
      if (!trimmedFull) return "";
      const trimmedPrior = priorText.trim();
      if (!trimmedPrior) return trimmedFull;
      if (!fullText.startsWith(priorText)) return trimmedFull;
      const appended = fullText.slice(priorText.length).trim();
      return appended || trimmedFull;
    },
    [],
  );

  React.useEffect(() => {
    refreshHistoryFromMessages();
  }, [greetingEnabled, refreshHistoryFromMessages]);

  // --- Message operations ---
  const messageOps = useMessageOperations({
    messages,
    history,
    historyId,
    setMessages,
    setHistory,
    setHistoryId,
    abortController,
    setAbortController,
    serverChatId,
    serverChatTitle,
    serverChatCharacterId,
    serverChatState,
    serverChatTopic,
    serverChatClusterId,
    serverChatSource,
    serverChatExternalRef,
    setServerChatId,
    setServerChatTitle,
    setServerChatCharacterId,
    setServerChatMetaLoaded,
    setServerChatState,
    setServerChatVersion,
    setServerChatTopic,
    setServerChatClusterId,
    setServerChatSource,
    setServerChatExternalRef,
    invalidateServerChatHistory,
    replyTarget,
    clearReplyTarget,
    setSelectedSystemPrompt,
    currentChatModelSettings,
    setContextFiles,
    notification,
    discardCurrentTurnOnAbortRef,
    selectedCharacter,
    scope,
  });

  // --- buildChatModeParams ---
  const buildChatModeParams = async (overrides: ChatModeOverrides = {}) => {
    const hasHistoryOverride = Object.prototype.hasOwnProperty.call(
      overrides,
      "historyId",
    );
    const resolvedServerChatId =
      overrides.serverChatId === undefined
        ? serverChatId
        : overrides.serverChatId;
    const resolvedHistoryId = hasHistoryOverride
      ? overrides.historyId
      : resolvedServerChatId && !temporaryChat
        ? await ensureServerChatHistoryId(
            resolvedServerChatId,
            serverChatTitle || undefined,
          )
        : historyId;

    const { getActorSettingsForChat } = await loadActorSettings();
    const actorSettings = await getActorSettingsForChat({
      historyId: resolvedHistoryId ?? historyId,
      serverChatId: resolvedServerChatId,
    });

    const effectiveSelectedModel = getEffectiveSelectedModel(
      overrides.selectedModel,
    );
    const resolvedSelectedSystemPrompt = Object.prototype.hasOwnProperty.call(
      overrides,
      "selectedSystemPrompt",
    )
      ? (overrides.selectedSystemPrompt as string | null)
      : selectedSystemPrompt;
    const resolvedToolChoice =
      overrides.toolChoice === "auto" ||
      overrides.toolChoice === "required" ||
      overrides.toolChoice === "none"
        ? overrides.toolChoice
        : toolChoice;
    const resolvedUseOCR =
      typeof overrides.useOCR === "boolean" ? overrides.useOCR : useOCR;
    const resolvedWebSearch =
      typeof overrides.webSearch === "boolean"
        ? overrides.webSearch
        : webSearch;

    return {
      selectedModel: effectiveSelectedModel || "",
      useOCR: resolvedUseOCR,
      selectedSystemPrompt: resolvedSelectedSystemPrompt,
      selectedKnowledge,
      toolChoice: resolvedToolChoice,
      currentChatModelSettings,
      setMessages,
      setIsSearchingInternet,
      saveMessageOnSuccess,
      saveMessageOnError,
      setHistory,
      setIsProcessing,
      setStreaming,
      setAbortController,
      historyId: resolvedHistoryId ?? historyId,
      setHistoryId,
      fileRetrievalEnabled,
      ragMediaIds,
      ragSearchMode,
      ragTopK,
      ragEnableGeneration,
      ragEnableCitations,
      ragSources,
      ragAdvancedOptions,
      setActionInfo,
      webSearch: resolvedWebSearch,
      actorSettings,
      systemPromptAppendix,
      messageSteeringPrompts: resolvedMessageSteeringPrompts,
      ...overrides,
    };
  };

  // --- Character chat mode ---
  const characterChatMode = createCharacterChatMode({
    t,
    notification,
    selectedCharacter,
    temporaryChat,
    historyId,
    serverChatId,
    serverChatCharacterId,
    serverChatState,
    serverChatTopic,
    serverChatClusterId,
    serverChatSource,
    serverChatExternalRef,
    currentChatModelSettings,
    setMessages,
    setHistory,
    setHistoryId,
    setIsProcessing,
    setStreaming,
    setAbortController,
    setServerChatId,
    setServerChatTitle,
    setServerChatCharacterId,
    setServerChatMetaLoaded,
    setServerChatState,
    setServerChatVersion,
    setServerChatTopic,
    setServerChatClusterId,
    setServerChatSource,
    setServerChatExternalRef,
    invalidateServerChatHistory,
    greetingEnabled,
    greetingSelectionId,
    greetingsChecksum,
    useCharacterDefault,
    directedCharacterId,
    resolvedMessageSteeringPrompts,
    getEffectiveSelectedModel,
    saveMessageOnSuccess,
    saveMessageOnError,
    discardCurrentTurnOnAbortRef,
    scope,
  });

  // --- Compare submit ---
  const {
    sendPerModelReply,
    createCompareBranch,
    buildCompareHistoryTitle,
  } = useCompareSubmit({
    t,
    notification,
    messages,
    history,
    historyId,
    temporaryChat,
    selectedKnowledge,
    fileRetrievalEnabled,
    ragMediaIds,
    uploadedFiles,
    contextFiles,
    documentContext,
    compareFeatureEnabled,
    currentChatModelSettings,
    setMessages,
    setHistory,
    setHistoryId,
    setStreaming,
    setIsProcessing,
    setAbortController,
    setContextFiles,
    setSelectedSystemPrompt,
    markCompareHistoryCreated,
    clearMessageSteering,
    invalidateServerChatHistory,
    serverChatId,
    setServerChatId: setServerChatId,
    setServerChatTitle: setServerChatTitle,
    buildChatModeParams,
    buildHistoryFromMessages,
    getEffectiveSelectedModel,
    resolvedMessageSteering,
  });

  // --- Validation ---
  const validateBeforeSubmitFn = () => {
    const effectiveSelectedModel = getEffectiveSelectedModel();
    if (compareModeActive) {
      const maxModels =
        typeof compareMaxModels === "number" && compareMaxModels > 0
          ? compareMaxModels
          : MAX_COMPARE_MODELS;

      if (!compareSelectedModels || compareSelectedModels.length === 0) {
        notification.error({
          message: t("error"),
          description: t(
            "playground:composer.validationCompareSelectModels",
            "Select at least one model to use in Compare mode.",
          ),
        });
        return false;
      }
      if (compareSelectedModels.length > maxModels) {
        notification.error({
          message: t("error"),
          description: t(
            "playground:composer.compareMaxModels",
            "You can compare up to {{limit}} models per turn.",
            { limit: maxModels },
          ),
        });
        return false;
      }
      return true;
    }
    return validateBeforeSubmit(effectiveSelectedModel || "", t, notification);
  };

  // --- onSubmit (main orchestrator) ---
  const onSubmit = async ({
    message,
    image,
    isRegenerate = false,
    messages: chatHistory,
    memory,
    controller,
    isContinue,
    docs,
    regenerateFromMessage,
    imageBackendOverride,
    userMessageType,
    assistantMessageType,
    imageGenerationRequest,
    imageGenerationRefine,
    imageGenerationPromptMode,
    imageGenerationSource,
    imageEventSyncPolicy,
    messageSteeringOverride,
    requestOverrides,
    continueOutputTarget = "chat",
    serverChatIdOverride,
  }: {
    message: string;
    image: string;
    isRegenerate?: boolean;
    isContinue?: boolean;
    messages?: Message[];
    memory?: ChatHistory;
    controller?: AbortController;
    docs?: ChatDocuments;
    regenerateFromMessage?: Message;
    imageBackendOverride?: string;
    userMessageType?: string;
    assistantMessageType?: string;
    imageGenerationRequest?: Partial<ImageGenerationRequestSnapshot>;
    imageGenerationRefine?: ImageGenerationRefineMetadata;
    imageGenerationPromptMode?: ImageGenerationPromptMode;
    imageGenerationSource?:
      | "slash-command"
      | "generate-modal"
      | "message-regen";
    imageEventSyncPolicy?: ImageGenerationEventSyncPolicy;
    messageSteeringOverride?: Partial<MessageSteeringState> | null;
    requestOverrides?: ChatModeOverrides;
    continueOutputTarget?: "chat" | "composer_input";
    serverChatIdOverride?: string | null;
  }) => {
    if (sendInFlightRef.current) return;
    sendInFlightRef.current = true;

    const effectiveSelectedModel = getEffectiveSelectedModel(
      requestOverrides?.selectedModel,
    );
    setStreaming(true);
    const trimmedImageBackendOverride =
      typeof imageBackendOverride === "string"
        ? imageBackendOverride.trim()
        : "";
    let signal: AbortSignal;
    let activeAbortController: AbortController;
    if (!controller) {
      const newController = new AbortController();
      signal = newController.signal;
      activeAbortController = newController;
      setAbortController(newController);
    } else {
      setAbortController(controller);
      signal = controller.signal;
      activeAbortController = controller;
    }

    const messageSteeringForTurn = messageSteeringOverride
      ? resolveMessageSteering({
          mode: messageSteeringOverride.mode ?? messageSteeringMode,
          forceNarrate:
            messageSteeringOverride.forceNarrate ?? messageSteeringForceNarrate,
        })
      : resolvedMessageSteering;
    if (messageSteeringForTurn.hadConflict) {
      notification.warning({
        message: t("warning", { defaultValue: "Warning" }),
        description: t(
          "playground:composer.steering.conflictResolved",
          "Impersonate user overrides Continue as user for this response.",
        ),
      });
    }
    const shouldConsumeSteering = hasActiveMessageSteering(
      messageSteeringForTurn,
    );
    let steeringApplied = false;
    const markSteeringApplied = () => {
      if (shouldConsumeSteering) {
        steeringApplied = true;
      }
    };

    const chatModeParams = await buildChatModeParams({
      ...(requestOverrides ?? {}),
      selectedModel: effectiveSelectedModel,
      messageSteering: messageSteeringForTurn,
      userMessageType,
      assistantMessageType,
      imageGenerationRequest,
      imageGenerationRefine,
      imageGenerationPromptMode,
      imageGenerationSource,
      imageEventSyncPolicy,
    }).catch((error) => {
      throw error;
    });
    const baseMessages = chatHistory || messages;
    const baseHistory = memory || history;
    const capturedReplyTargetId = replyTarget?.id ?? null;
    const replyActive =
      Boolean(replyTarget) &&
      !compareModeActive &&
      !isRegenerate &&
      !isContinue &&
      !selectedCharacter?.id;
    const replyOverrides = replyActive
      ? (() => {
          const userMessageId = generateID();
          const assistantMessageId = generateID();
          return {
            userMessageId,
            assistantMessageId,
            userParentMessageId: replyTarget?.id ?? null,
            assistantParentMessageId: userMessageId,
          };
        })()
      : {};
    const chatModeParamsWithReply = replyActive
      ? { ...chatModeParams, ...replyOverrides }
      : chatModeParams;
    const chatModeParamsWithRegen = {
      ...chatModeParamsWithReply,
      regenerateFromMessage: isRegenerate ? regenerateFromMessage : undefined,
    };

    try {
      if (isContinue) {
        const continueMessages = chatHistory || messages;
        const continueHistory = memory || history;
        const continueTargetMessage =
          continueMessages[continueMessages.length - 1];
        const priorAssistantText = continueTargetMessage?.message || "";
        const priorHistorySnapshot = continueHistory.map((entry) => ({
          ...entry,
        }));

        markSteeringApplied();
        await continueChatMode(
          continueMessages,
          continueHistory,
          signal,
          chatModeParams,
        );

        if (continueOutputTarget === "composer_input") {
          const currentMessages = messagesRef.current;
          const continuedMessage = continueTargetMessage?.id
            ? currentMessages.find(
                (entry) => entry.id === continueTargetMessage.id,
              )
            : currentMessages[currentMessages.length - 1];
          const continuedText = continuedMessage?.message || "";
          const continuationDraft = extractContinuationDraft(
            continuedText,
            priorAssistantText,
          );

          setSelectedQuickPrompt(continuationDraft);

          if (continueTargetMessage?.id) {
            const targetId = continueTargetMessage.id;
            setMessages((prev) =>
              prev.map((entry) =>
                entry.id === targetId
                  ? updateActiveVariant(entry, { message: priorAssistantText })
                  : entry,
              ),
            );
          } else {
            setMessages((prev) => {
              if (prev.length === 0) return prev;
              const next = [...prev];
              const lastIndex = next.length - 1;
              next[lastIndex] = updateActiveVariant(next[lastIndex], {
                message: priorAssistantText,
              });
              return next;
            });
          }

          setHistory(priorHistorySnapshot);

          const resolvedHistoryId =
            typeof chatModeParams.historyId === "string" &&
            chatModeParams.historyId.length > 0
              ? chatModeParams.historyId
              : historyId;
          if (
            resolvedHistoryId &&
            resolvedHistoryId !== "temp" &&
            continueTargetMessage?.id
          ) {
            await updateMessage(
              resolvedHistoryId,
              continueTargetMessage.id,
              priorAssistantText,
            ).catch(() => null);
          }
        }

        return;
      }

      const hasExplicitImageBackend = trimmedImageBackendOverride.length > 0;
      const imageBackendCandidates = hasExplicitImageBackend
        ? [trimmedImageBackendOverride]
        : resolveImageBackendCandidates(
            currentChatModelSettings?.apiProvider,
            effectiveSelectedModel,
          );
      if (hasExplicitImageBackend || imageBackendCandidates.length > 0) {
        const resolvedImageModelLabel = hasExplicitImageBackend
          ? trimmedImageBackendOverride ||
            (effectiveSelectedModel || "").trim() ||
            currentChatModelSettings?.apiProvider ||
            "image-generation"
          : (effectiveSelectedModel || "").trim() ||
            currentChatModelSettings?.apiProvider ||
            "image-generation";
        const enhancedChatModeParams = {
          ...chatModeParamsWithRegen,
          selectedModel: resolvedImageModelLabel,
          uploadedFiles: hasExplicitImageBackend ? [] : uploadedFiles,
          imageBackendOverride: hasExplicitImageBackend
            ? trimmedImageBackendOverride
            : undefined,
        };
        await normalChatMode(
          message,
          image,
          isRegenerate,
          baseMessages,
          baseHistory,
          signal,
          enhancedChatModeParams,
        );
        return;
      }

      if (contextFiles.length > 0) {
        markSteeringApplied();
        await documentChatMode(
          message,
          image,
          isRegenerate,
          chatHistory || messages,
          memory || history,
          signal,
          contextFiles,
          chatModeParamsWithRegen,
        );
        return;
      }

      if (docs?.length > 0 || documentContext?.length > 0) {
        const processingTabs = docs || documentContext || [];
        if (docs?.length > 0) {
          setDocumentContext(
            Array.from(new Set([...(documentContext || []), ...docs])),
          );
        }
        markSteeringApplied();
        await tabChatMode(
          message,
          image,
          processingTabs,
          isRegenerate,
          chatHistory || messages,
          memory || history,
          signal,
          chatModeParamsWithRegen,
        );
        return;
      }

      const hasScopedRagMediaIds =
        Array.isArray(ragMediaIds) && ragMediaIds.length > 0;
      const shouldUseRag =
        Boolean(selectedKnowledge) ||
        (fileRetrievalEnabled && hasScopedRagMediaIds);
      if (shouldUseRag) {
        markSteeringApplied();
        await ragMode(
          message,
          image,
          isRegenerate,
          chatHistory || messages,
          memory || history,
          signal,
          chatModeParamsWithRegen,
        );
      } else {
        const enhancedChatModeParams = {
          ...chatModeParamsWithRegen,
          uploadedFiles: uploadedFiles,
        };
        const baseMessages = chatHistory || messages;
        const baseHistory = memory || history;

        if (!compareModeActive) {
          const resolvedSelectedCharacter = await resolveSelectedCharacter();
          if (resolvedSelectedCharacter?.id) {
            const resolvedModel = effectiveSelectedModel?.trim();
            if (!resolvedModel) {
              notification.error({
                message: t("error"),
                description: t("validationSelectModel"),
              });
              setIsProcessing(false);
              setStreaming(false);
              setAbortController(null);
              return;
            }
            markSteeringApplied();
            await characterChatMode({
              message,
              image,
              isRegenerate,
              messages: baseMessages,
              history: baseHistory,
              signal,
              model: resolvedModel,
              regenerateFromMessage,
              character: resolvedSelectedCharacter,
              controller: activeAbortController,
              messageSteering: messageSteeringForTurn,
              serverChatIdOverride,
            });
            return;
          }

          if (isPersonaAssistantSelection(selectedAssistant)) {
            const resolvedModel = effectiveSelectedModel?.trim();
            if (!resolvedModel) {
              notification.error({
                message: t("error"),
                description: t("validationSelectModel"),
              });
              setIsProcessing(false);
              setStreaming(false);
              setAbortController(null);
              return;
            }

            const personaServerChat = await ensurePersonaServerChatWithState({
              assistant: selectedAssistant,
              serverChatIdOverride,
            });
            const assistantIdentity = {
              name: selectedAssistant.name,
              avatarUrl:
                typeof selectedAssistant.avatar_url === "string"
                  ? selectedAssistant.avatar_url
                  : undefined,
            };
            markSteeringApplied();
            await normalChatMode(
              message,
              image,
              isRegenerate,
              baseMessages,
              baseHistory,
              signal,
              {
                ...enhancedChatModeParams,
                assistantIdentity,
                historyId: personaServerChat.historyId,
                saveMessageOnSuccess: (data: SaveMessageData) =>
                  saveMessageOnSuccess({
                    ...data,
                    conversationId: personaServerChat.chatId,
                  }),
              },
            );
            return;
          }
        }

        if (!compareModeActive) {
          markSteeringApplied();
          await normalChatMode(
            message,
            image,
            isRegenerate,
            baseMessages,
            baseHistory,
            signal,
            enhancedChatModeParams,
          );
        } else {
          const maxModels =
            typeof compareMaxModels === "number" && compareMaxModels > 0
              ? compareMaxModels
              : MAX_COMPARE_MODELS;

          const modelsRaw =
            compareSelectedModels && compareSelectedModels.length > 0
              ? compareSelectedModels
              : effectiveSelectedModel
                ? [effectiveSelectedModel]
                : [];
          if (modelsRaw.length === 0) {
            throw new Error("No models selected for Compare mode");
          }
          const uniqueModels = Array.from(new Set(modelsRaw));
          const models =
            uniqueModels.length > maxModels
              ? uniqueModels.slice(0, maxModels)
              : uniqueModels;

          if (uniqueModels.length > maxModels) {
            notification.warning({
              message: t("error"),
              description: t(
                "playground:composer.compareMaxModelsTrimmed",
                "Compare is limited to {{limit}} models per turn. Using the first {{limit}} selected models.",
                { count: maxModels, limit: maxModels },
              ),
            });
          }
          const clusterId = generateID();
          const compareUserMessageId = generateID();
          const lastMessage = baseMessages[baseMessages.length - 1];
          const compareUserParentMessageId = lastMessage?.id || null;
          const resolvedImage =
            image.length > 0
              ? image.startsWith("data:")
                ? image
                : image.includes(",")
                  ? `data:image/jpeg;base64,${image.split(",")[1]}`
                  : `data:image/jpeg;base64,${image}`
              : "";
          const compareUserMessage: Message = {
            isBot: false,
            name: "You",
            message,
            sources: [],
            images: resolvedImage ? [resolvedImage] : [],
            createdAt: Date.now(),
            id: compareUserMessageId,
            messageType: "compare:user",
            clusterId,
            parentMessageId: compareUserParentMessageId,
            documents:
              uploadedFiles?.map((file) => ({
                type: "file",
                filename: file.filename,
                fileSize: file.size,
                processed: file.processed,
              })) || [],
          };

          setMessages((prev) => [...prev, compareUserMessage]);
          setHistory((prev) => [
            ...prev,
            {
              role: "user" as const,
              content: compareUserMessage.message,
              image: compareUserMessage.images?.[0],
              messageType: compareUserMessage.messageType,
            },
          ]);

          let activeHistoryId = historyId;
          if (temporaryChat) {
            if (historyId !== "temp") {
              setHistoryId("temp");
            }
            activeHistoryId = "temp";
          } else if (!activeHistoryId) {
            const title = await generateTitle(
              uniqueModels[0] || effectiveSelectedModel || "",
              message,
              message,
            );
            const compareTitle = buildCompareHistoryTitle(title);
            const newHistory = await saveHistory(compareTitle, false, "web-ui");
            updatePageTitle(compareTitle);
            activeHistoryId = newHistory.id;
            setHistoryId(newHistory.id);
            markCompareHistoryCreated(newHistory.id);
          }

          if (!temporaryChat && activeHistoryId) {
            await saveMessage({
              id: compareUserMessageId,
              history_id: activeHistoryId,
              name: effectiveSelectedModel || uniqueModels[0] || "You",
              role: "user",
              content: message,
              images: resolvedImage ? [resolvedImage] : [],
              time: 1,
              message_type: "compare:user",
              clusterId,
              parent_message_id: compareUserParentMessageId,
              documents:
                uploadedFiles?.map((file) => ({
                  type: "file",
                  filename: file.filename,
                  fileSize: file.size,
                  processed: file.processed,
                })) || [],
            });
          }

          setIsProcessing(true);

          const compareChatModeParams = await buildChatModeParams({
            historyId: activeHistoryId,
            setHistory: () => {},
            setStreaming: () => {},
            setIsProcessing: () => {},
            setAbortController: () => {},
            messageSteering: messageSteeringForTurn,
          });
          const compareEnhancedParams = {
            ...compareChatModeParams,
            uploadedFiles: uploadedFiles,
          };

          const comparePromises = models.map((modelId) => {
            const historyForModel = buildHistoryForModel(
              baseMessages,
              modelId,
              buildHistoryFromMessages,
            );
            return normalChatMode(
              message,
              image,
              true,
              baseMessages,
              baseHistory,
              signal,
              {
                ...compareEnhancedParams,
                selectedModel: modelId,
                clusterId,
                assistantMessageType: "compare:reply",
                modelIdOverride: modelId,
                assistantParentMessageId: compareUserMessageId,
                historyForModel,
              },
            ).catch((e) => {
              const errorMessage =
                e instanceof Error ? e.message : t("somethingWentWrong");
              notification.error({
                message: t("error"),
                description: errorMessage,
              });
            });
          });

          markSteeringApplied();
          await Promise.allSettled(comparePromises);
          refreshHistoryFromMessages();
          setIsProcessing(false);
          setStreaming(false);
          setAbortController(null);
        }
      }
    } catch (e) {
      const errorMessage =
        e instanceof Error ? e.message : t("somethingWentWrong");
      notification.error({
        message: t("error"),
        description: errorMessage,
      });
      setIsProcessing(false);
      setStreaming(false);
      setAbortController(null);
    } finally {
      sendInFlightRef.current = false;
      if (replyActive && capturedReplyTargetId != null) {
        const currentReplyTarget = useStoreMessageOption.getState().replyTarget;
        if (currentReplyTarget?.id === capturedReplyTargetId) {
          clearReplyTarget();
        }
      }
      if (steeringApplied) {
        clearMessageSteering();
      }
    }
  };

  // --- Bind submit into message operations ---
  const { editMessage, regenerateLastMessage } = messageOps.bindSubmit(
    onSubmit,
    validateBeforeSubmitFn,
  );

  return {
    onSubmit,
    sendPerModelReply,
    regenerateLastMessage,
    stopStreamingRequest: messageOps.stopStreamingRequest,
    editMessage,
    deleteMessage: messageOps.deleteMessage,
    toggleMessagePinned: messageOps.toggleMessagePinned,
    createChatBranch: messageOps.createChatBranch,
    createCompareBranch,
  };
};
