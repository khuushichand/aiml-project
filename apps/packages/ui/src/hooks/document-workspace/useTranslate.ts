import { useMutation } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"

export interface TranslateParams {
  text: string
  targetLanguage?: string
  model?: string
  provider?: string
}

export interface TranslateResult {
  translated_text: string
  target_language: string
  model_used: string
  detected_source_language?: string
}

/**
 * Hook for translating text via the translation API.
 *
 * @returns Mutation for translating text
 *
 * @example
 * const { mutateAsync: translate, isPending } = useTranslate()
 *
 * const result = await translate({
 *   text: "Hello world",
 *   targetLanguage: "Spanish"
 * })
 */
export function useTranslate() {
  return useMutation<TranslateResult, Error, TranslateParams>({
    mutationFn: async ({ text, targetLanguage = "English", model, provider }) => {
      return await tldwClient.translate(text, targetLanguage, { model, provider })
    }
  })
}
