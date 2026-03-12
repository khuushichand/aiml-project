export { usePdfOutline, useDocumentPageCount } from "./usePdfOutline"
export { useDocumentMetadata } from "./useDocumentMetadata"
export { useDocumentChat } from "./useDocumentChat"
export type { UseDocumentChatReturn } from "./useDocumentChat"
export {
  useDocumentInsights,
  useGenerateInsightsMutation,
  INSIGHT_CATEGORY_INFO,
} from "./useDocumentInsights"
export type {
  InsightCategory,
  InsightItem,
  DocumentInsightsResponse,
  GenerateInsightsOptions,
} from "./useDocumentInsights"
export {
  useDocumentReferences,
  getReferenceUrl,
  formatCitationCount,
} from "./useDocumentReferences"
export type {
  ReferenceEntry,
  DocumentReferencesResponse,
} from "./useDocumentReferences"
export { usePdfSearch } from "./usePdfSearch"
export type { SearchResult } from "./usePdfSearch"
export { useTextSelection } from "./useTextSelection"
export type { TextSelection } from "./useTextSelection"
export { useTranslate } from "./useTranslate"
export type { TranslateParams, TranslateResult } from "./useTranslate"
export { useDocumentFigures } from "./useDocumentFigures"
export type { DocumentFigure, DocumentFiguresResponse } from "./useDocumentFigures"
export {
  useAnnotations,
  useCreateAnnotation,
  useUpdateAnnotation,
  useDeleteAnnotation,
} from "./useAnnotations"
export type {
  AnnotationResponse,
  AnnotationsListResponse,
} from "./useAnnotations"
export {
  useAnnotationSync,
  useAnnotationSyncOnClose,
} from "./useAnnotationSync"
export {
  useReadingProgress,
  useUpdateReadingProgress,
  useReadingProgressAutoSave,
  useReadingProgressSaveOnClose,
} from "./useReadingProgress"
export type { ReadingProgress, ReadingProgressNotFound } from "./useReadingProgress"
export { useEpubReader, useEpubRendition } from "./useEpubReader"
export type { EpubLocation, EpubReaderState, UseEpubReaderReturn } from "./useEpubReader"
export { useEpubOutline, flattenTocItems, findTocItemByHref } from "./useEpubOutline"
export { useEpubSearch } from "./useEpubSearch"
export type { EpubSearchResult, UseEpubSearchReturn } from "./useEpubSearch"
export {
  useEpubSettings,
  EPUB_THEMES,
  THEME_INFO,
  SCROLL_MODE_INFO,
} from "./useEpubSettings"
export { useDocumentTTS } from "./useDocumentTTS"
export type {
  TTSVoice,
  TTSState,
  UseDocumentTTSReturn,
} from "./useDocumentTTS"
export {
  useCitation,
  CITATION_FORMAT_INFO,
  generateCitation,
  formatMLA,
  formatAPA,
  formatChicago,
  formatHarvard,
  formatIEEE,
} from "./useCitation"
export type { CitationFormat } from "./useCitation"
export {
  useDocumentQuiz,
  useQuizHistory,
  QUESTION_TYPE_INFO,
  DIFFICULTY_INFO,
} from "./useDocumentQuiz"
export type {
  QuestionType,
  DifficultyLevel,
  QuizGenerationOptions,
  QuizQuestion,
  QuizResponse,
} from "./useDocumentQuiz"
export type { QuizHistoryEntry } from "./offlineQueue"
export { useResizablePanel } from "./useResizablePanel"
