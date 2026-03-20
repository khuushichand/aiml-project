import React from "react";
import { useStorage } from "@plasmohq/storage/hook";
import {
  DEFAULT_RAG_SETTINGS,
  toRagAdvancedOptions,
  type RagSettings,
} from "@/services/rag/unified-rag";

/**
 * Hydrates RAG search defaults from browser storage into Zustand store
 * when starting a new chat (no historyId, serverChatId, or messages).
 */
export const useRagSettings = ({
  historyId,
  serverChatId,
  messagesLength,
  setRagSearchMode,
  setRagTopK,
  setRagEnableGeneration,
  setRagEnableCitations,
  setRagSources,
  setRagAdvancedOptions,
}: {
  historyId: string | null;
  serverChatId: string | null;
  messagesLength: number;
  setRagSearchMode: (mode: "hybrid" | "vector" | "fts") => void;
  setRagTopK: (k: number) => void;
  setRagEnableGeneration: (enabled: boolean) => void;
  setRagEnableCitations: (enabled: boolean) => void;
  setRagSources: (sources: string[]) => void;
  setRagAdvancedOptions: (options: Record<string, unknown>) => void;
}) => {
  const [storedRagSettings] = useStorage<RagSettings>(
    "ragSearchSettingsV2",
    DEFAULT_RAG_SETTINGS,
  );

  const lastHydratedRagDefaultsRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (historyId || serverChatId || messagesLength > 0) {
      lastHydratedRagDefaultsRef.current = null;
      return;
    }

    const normalizedSettings = {
      ...DEFAULT_RAG_SETTINGS,
      ...(storedRagSettings || {}),
    };
    const serialized = JSON.stringify(normalizedSettings);
    if (serialized === lastHydratedRagDefaultsRef.current) {
      return;
    }
    lastHydratedRagDefaultsRef.current = serialized;

    const searchMode =
      normalizedSettings.search_mode === "fts" ||
      normalizedSettings.search_mode === "vector" ||
      normalizedSettings.search_mode === "hybrid"
        ? normalizedSettings.search_mode
        : DEFAULT_RAG_SETTINGS.search_mode;
    const topKValue =
      typeof normalizedSettings.top_k === "number" &&
      Number.isFinite(normalizedSettings.top_k)
        ? normalizedSettings.top_k
        : DEFAULT_RAG_SETTINGS.top_k;
    const sourcesValue =
      Array.isArray(normalizedSettings.sources) &&
      normalizedSettings.sources.every((source) => typeof source === "string")
        ? normalizedSettings.sources
        : DEFAULT_RAG_SETTINGS.sources;

    setRagSearchMode(searchMode);
    setRagTopK(topKValue);
    setRagEnableGeneration(Boolean(normalizedSettings.enable_generation));
    setRagEnableCitations(Boolean(normalizedSettings.enable_citations));
    setRagSources(sourcesValue);
    setRagAdvancedOptions(toRagAdvancedOptions(normalizedSettings));
  }, [
    historyId,
    messagesLength,
    serverChatId,
    setRagAdvancedOptions,
    setRagEnableCitations,
    setRagEnableGeneration,
    setRagSearchMode,
    setRagSources,
    setRagTopK,
    storedRagSettings,
  ]);
};
