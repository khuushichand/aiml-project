import React from "react";
import { useStoreMessageOption } from "@/store/option";
import { useStorage } from "@plasmohq/storage/hook";

/**
 * Normalizes a model string: trims whitespace, returns null for empty/non-string values.
 */
export const normalizeSelectedModel = (
  value: string | null | undefined,
): string | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
};

/**
 * Consolidated model selection hook.
 *
 * Encapsulates the 3-way sync between:
 * - Zustand store (`useStoreMessageOption.selectedModel`)
 * - Browser storage (`useStorage("selectedModel")`)
 * - Derived `selectedModel` value (store takes precedence, storage as fallback)
 */
export const useSelectedModel = () => {
  const selectedModelFromStore = useStoreMessageOption((s) => s.selectedModel);
  const setSelectedModelInStore = useStoreMessageOption(
    (s) => s.setSelectedModel,
  );
  const [
    storedSelectedModel,
    setStoredSelectedModel,
    selectedModelStorageMeta,
  ] = useStorage<string | null>("selectedModel", null);

  const selectedModel = React.useMemo(
    () =>
      normalizeSelectedModel(selectedModelFromStore) ??
      normalizeSelectedModel(storedSelectedModel),
    [selectedModelFromStore, storedSelectedModel],
  );

  const setSelectedModel = React.useCallback(
    (
      nextOrUpdater:
        | string
        | null
        | ((current: string | null) => string | null),
    ) => {
      const resolved =
        typeof nextOrUpdater === "function"
          ? nextOrUpdater(selectedModel)
          : nextOrUpdater;
      const normalized = normalizeSelectedModel(resolved);
      setSelectedModelInStore(normalized);
      void setStoredSelectedModel(normalized);
    },
    [selectedModel, setSelectedModelInStore, setStoredSelectedModel],
  );

  // Sync effect: hydrate store from storage or push store to storage
  React.useEffect(() => {
    const normalizedStoreModel = normalizeSelectedModel(selectedModelFromStore);
    const normalizedStoredModel = normalizeSelectedModel(storedSelectedModel);

    if (!normalizedStoreModel && normalizedStoredModel) {
      setSelectedModelInStore(normalizedStoredModel);
      return;
    }

    if (normalizedStoreModel !== normalizedStoredModel) {
      void setStoredSelectedModel(normalizedStoreModel);
    }
  }, [
    selectedModelFromStore,
    setSelectedModelInStore,
    setStoredSelectedModel,
    storedSelectedModel,
  ]);

  return {
    selectedModel,
    setSelectedModel,
    selectedModelIsLoading: selectedModelStorageMeta.isLoading,
  };
};
