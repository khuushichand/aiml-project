/**
 * KnowledgeQA - Research-grade question-answering interface
 *
 * A Perplexity-style Q&A experience combining discoverability with
 * the full power of the RAG pipeline.
 */

import React, { useState } from "react"
import { KnowledgeQAProvider, useKnowledgeQA } from "./KnowledgeQAProvider"
import { SearchBar } from "./SearchBar"
import { AnswerPanel } from "./AnswerPanel"
import { SourceList } from "./SourceList"
import { FollowUpInput } from "./FollowUpInput"
import { HistorySidebar } from "./HistorySidebar"
import { SettingsPanel } from "./SettingsPanel"
import { ExportDialog } from "./ExportDialog"
import { cn } from "@/lib/utils"
import { useServerOnline } from "@/hooks/useServerOnline"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { WifiOff, AlertCircle, BookOpen, Download } from "lucide-react"

// Main page component (inner, uses context)
function KnowledgeQAContent() {
  const { settingsPanelOpen, setSettingsPanelOpen, results, answer } = useKnowledgeQA()
  const [exportDialogOpen, setExportDialogOpen] = useState(false)
  const online = useServerOnline()
  const { capabilities, loading: capabilitiesLoading } = useServerCapabilities()

  // Check if RAG is supported
  const hasRag = capabilities?.hasRag ?? true

  // Offline state
  if (!online) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <WifiOff className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
          <h2 className="text-xl font-semibold mb-2">Server Offline</h2>
          <p className="text-muted-foreground">
            Cannot connect to the server. Please ensure the tldw server is running
            and try again.
          </p>
        </div>
      </div>
    )
  }

  // No RAG support
  if (!capabilitiesLoading && !hasRag) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
          <h2 className="text-xl font-semibold mb-2">RAG Not Available</h2>
          <p className="text-muted-foreground">
            Knowledge search requires the RAG module to be enabled on the server.
            Please check your server configuration.
          </p>
        </div>
      </div>
    )
  }

  const hasResults = results.length > 0 || answer

  return (
    <div className="flex h-full">
      {/* History sidebar */}
      <HistorySidebar />

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Search area */}
        <div
          className={cn(
            "flex flex-col items-center justify-center transition-all duration-300",
            hasResults ? "pt-6 pb-4" : "flex-1"
          )}
        >
          {/* Logo/branding when no results */}
          {!hasResults && (
            <div className="mb-8 text-center">
              <BookOpen className="w-16 h-16 mx-auto mb-4 text-primary" />
              <h1 className="text-3xl font-bold mb-2">Knowledge QA</h1>
              <p className="text-muted-foreground max-w-md">
                Ask questions about your documents and get AI-powered answers
                with citations from your knowledge base.
              </p>
            </div>
          )}

          <SearchBar />
        </div>

        {/* Results area */}
        {hasResults && (
          <div className="flex-1 overflow-y-auto px-6 pb-6">
            <div className="max-w-4xl mx-auto space-y-6">
              {/* Export button */}
              <div className="flex justify-end">
                <button
                  onClick={() => setExportDialogOpen(true)}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Export
                </button>
              </div>

              <AnswerPanel />
              <SourceList />
              <FollowUpInput />
            </div>
          </div>
        )}
      </div>

      {/* Settings panel (drawer) */}
      <SettingsPanel
        open={settingsPanelOpen}
        onClose={() => setSettingsPanelOpen(false)}
      />

      {/* Export dialog */}
      <ExportDialog
        open={exportDialogOpen}
        onClose={() => setExportDialogOpen(false)}
      />
    </div>
  )
}

// Export the wrapped component
export function KnowledgeQA() {
  return (
    <KnowledgeQAProvider>
      <KnowledgeQAContent />
    </KnowledgeQAProvider>
  )
}

// Also export individual components for flexibility
export { KnowledgeQAProvider, useKnowledgeQA } from "./KnowledgeQAProvider"
export { SearchBar } from "./SearchBar"
export { AnswerPanel } from "./AnswerPanel"
export { SourceCard } from "./SourceCard"
export { SourceList } from "./SourceList"
export { FollowUpInput } from "./FollowUpInput"
export { HistorySidebar } from "./HistorySidebar"
export { SettingsPanel } from "./SettingsPanel"
export { ExportDialog } from "./ExportDialog"
export type * from "./types"
