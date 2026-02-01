import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"

/**
 * Categories of insights that can be extracted from a document.
 */
export type InsightCategory =
  | "research_gap"
  | "research_question"
  | "motivation"
  | "methods"
  | "key_findings"
  | "limitations"
  | "future_work"
  | "summary"

const INSIGHT_CATEGORIES: InsightCategory[] = [
  "research_gap",
  "research_question",
  "motivation",
  "methods",
  "key_findings",
  "limitations",
  "future_work",
  "summary"
]

const normalizeInsightCategory = (value: string): InsightCategory =>
  INSIGHT_CATEGORIES.includes(value as InsightCategory)
    ? (value as InsightCategory)
    : "summary"

/**
 * A single insight extracted from the document.
 */
export interface InsightItem {
  category: InsightCategory
  title: string
  content: string
  confidence?: number
}

/**
 * Response from the insights generation endpoint.
 */
export interface DocumentInsightsResponse {
  media_id: number
  insights: InsightItem[]
  model_used: string
  cached: boolean
}

/**
 * Options for generating insights.
 */
export interface GenerateInsightsOptions {
  categories?: InsightCategory[]
  model?: string
  max_content_length?: number
  force?: boolean
}

/**
 * Hook to fetch cached document insights.
 *
 * Note: Insights are generated on-demand and cached.
 * Use `useGenerateInsightsMutation` to trigger generation.
 *
 * @param mediaId - The media ID to fetch insights for (null to disable query)
 * @returns Query result with insights, loading state, and error
 */
export function useDocumentInsights(mediaId: number | null) {
  return useQuery({
    queryKey: ["document-insights", mediaId],
    queryFn: async (): Promise<DocumentInsightsResponse | null> => {
      if (mediaId === null) return null
      // This will return cached insights or generate new ones
      const response = await tldwClient.generateDocumentInsights(mediaId)
      return {
        ...response,
        insights: response.insights.map((insight) => ({
          ...insight,
          category: normalizeInsightCategory(insight.category)
        }))
      }
    },
    // Insights are generated on-demand, so we don't auto-fetch
    enabled: false,
    staleTime: 30 * 60 * 1000, // Cache for 30 minutes
    retry: 1,
    refetchOnWindowFocus: false,
  })
}

/**
 * Mutation hook to generate document insights on-demand.
 *
 * This triggers LLM analysis of the document content.
 * Results are cached in the query cache.
 *
 * @returns Mutation with mutate function, loading state, and error
 */
export function useGenerateInsightsMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      mediaId,
      options,
    }: {
      mediaId: number
      options?: GenerateInsightsOptions
    }): Promise<DocumentInsightsResponse> => {
      const response = await tldwClient.generateDocumentInsights(mediaId, options)
      return {
        ...response,
        insights: response.insights.map((insight) => ({
          ...insight,
          category: normalizeInsightCategory(insight.category)
        }))
      }
    },
    onSuccess: (data, variables) => {
      // Update the cache with the generated insights
      queryClient.setQueryData(
        ["document-insights", variables.mediaId],
        data
      )
    },
  })
}

/**
 * Helper to get display information for insight categories.
 */
export const INSIGHT_CATEGORY_INFO: Record<
  InsightCategory,
  { label: string; description: string }
> = {
  research_gap: {
    label: "Research Gap",
    description: "What problem or gap this work addresses",
  },
  research_question: {
    label: "Research Question",
    description: "The main research question",
  },
  motivation: {
    label: "Motivation",
    description: "Why this research is important",
  },
  methods: {
    label: "Methods",
    description: "Methods or approaches used",
  },
  key_findings: {
    label: "Key Findings",
    description: "Main results or findings",
  },
  limitations: {
    label: "Limitations",
    description: "Limitations or caveats",
  },
  future_work: {
    label: "Future Work",
    description: "Suggested future work",
  },
  summary: {
    label: "Summary",
    description: "Brief document summary",
  },
}
