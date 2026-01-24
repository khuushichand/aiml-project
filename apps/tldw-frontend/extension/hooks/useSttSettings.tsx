import { useStorage } from "@plasmohq/storage/hook"
import { STT_DEFAULTS } from "@/config/ui-constants"

/**
 * STT (Speech-to-Text) settings consolidated into a single hook.
 * Previously these were 15+ separate useStorage calls scattered in form.tsx.
 */
export interface SttSettings {
  // Core settings
  model: string
  temperature: number
  task: string
  responseFormat: string
  timestampGranularities: string
  prompt: string
  useSegmentation: boolean

  // Segmentation parameters
  segK: number
  segMinSegmentSize: number
  segLambdaBalance: number
  segUtteranceExpansionWidth: number
  segEmbeddingsProvider: string
  segEmbeddingsModel: string
}

export const useSttSettings = (): SttSettings => {
  const [model] = useStorage("sttModel", STT_DEFAULTS.MODEL)
  const [temperature] = useStorage("sttTemperature", STT_DEFAULTS.TEMPERATURE)
  const [task] = useStorage("sttTask", STT_DEFAULTS.TASK)
  const [responseFormat] = useStorage(
    "sttResponseFormat",
    STT_DEFAULTS.RESPONSE_FORMAT
  )
  const [timestampGranularities] = useStorage(
    "sttTimestampGranularities",
    STT_DEFAULTS.TIMESTAMP_GRANULARITIES
  )
  const [prompt] = useStorage("sttPrompt", STT_DEFAULTS.PROMPT)
  const [useSegmentation] = useStorage("sttUseSegmentation", false)

  // Segmentation parameters
  const [segK] = useStorage("sttSegK", STT_DEFAULTS.SEG_K)
  const [segMinSegmentSize] = useStorage(
    "sttSegMinSegmentSize",
    STT_DEFAULTS.SEG_MIN_SEGMENT_SIZE
  )
  const [segLambdaBalance] = useStorage(
    "sttSegLambdaBalance",
    STT_DEFAULTS.SEG_LAMBDA_BALANCE
  )
  const [segUtteranceExpansionWidth] = useStorage(
    "sttSegUtteranceExpansionWidth",
    STT_DEFAULTS.SEG_UTTERANCE_EXPANSION_WIDTH
  )
  const [segEmbeddingsProvider] = useStorage(
    "sttSegEmbeddingsProvider",
    STT_DEFAULTS.SEG_EMBEDDINGS_PROVIDER
  )
  const [segEmbeddingsModel] = useStorage(
    "sttSegEmbeddingsModel",
    STT_DEFAULTS.SEG_EMBEDDINGS_MODEL
  )

  return {
    model: model ?? STT_DEFAULTS.MODEL,
    temperature: temperature ?? STT_DEFAULTS.TEMPERATURE,
    task: task ?? STT_DEFAULTS.TASK,
    responseFormat: responseFormat ?? STT_DEFAULTS.RESPONSE_FORMAT,
    timestampGranularities:
      timestampGranularities ?? STT_DEFAULTS.TIMESTAMP_GRANULARITIES,
    prompt: prompt ?? STT_DEFAULTS.PROMPT,
    useSegmentation: useSegmentation ?? false,
    segK: segK ?? STT_DEFAULTS.SEG_K,
    segMinSegmentSize:
      segMinSegmentSize ?? STT_DEFAULTS.SEG_MIN_SEGMENT_SIZE,
    segLambdaBalance:
      segLambdaBalance ?? STT_DEFAULTS.SEG_LAMBDA_BALANCE,
    segUtteranceExpansionWidth:
      segUtteranceExpansionWidth ?? STT_DEFAULTS.SEG_UTTERANCE_EXPANSION_WIDTH,
    segEmbeddingsProvider:
      segEmbeddingsProvider ?? STT_DEFAULTS.SEG_EMBEDDINGS_PROVIDER,
    segEmbeddingsModel:
      segEmbeddingsModel ?? STT_DEFAULTS.SEG_EMBEDDINGS_MODEL
  }
}
