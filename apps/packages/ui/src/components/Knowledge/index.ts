/**
 * Knowledge Search Panel
 *
 * A 4-tab interface for RAG (Retrieval-Augmented Generation) functionality:
 * - QA Search: Full RAG pipeline with generated answers and source chunks
 * - File Search: Media library search for document discovery and attachment
 * - Settings: Configure RAG parameters (quality, generation, citations, etc.)
 * - Context: Manage attached tabs, files, and pinned results
 */

export { KnowledgePanel } from "./KnowledgePanel"
export type { KnowledgePanelProps, KnowledgeTab } from "./KnowledgePanel"
