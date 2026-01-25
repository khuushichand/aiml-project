/**
 * SettingsPanel - RAG settings drawer
 */

import React from "react"
import { X, Settings, Zap, Scale, Brain, Beaker, RotateCcw } from "lucide-react"
import { useKnowledgeQA } from "../KnowledgeQAProvider"
import { PresetSelector } from "./PresetSelector"
import { BasicSettings } from "./BasicSettings"
import { ExpertSettings } from "./ExpertSettings"
import { cn } from "@/lib/utils"

type SettingsPanelProps = {
  open: boolean
  onClose: () => void
  className?: string
}

export function SettingsPanel({ open, onClose, className }: SettingsPanelProps) {
  const { expertMode, toggleExpertMode, resetSettings, preset } = useKnowledgeQA()

  if (!open) {
    return null
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className={cn(
          "fixed right-0 top-0 h-full w-96 max-w-full",
          "bg-background border-l border-border shadow-xl",
          "flex flex-col z-50",
          "animate-in slide-in-from-right duration-200",
          className
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-muted-foreground" />
            <span className="font-semibold">RAG Settings</span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Preset selector */}
          <div className="p-4 border-b border-border">
            <PresetSelector />
          </div>

          {/* Mode toggle */}
          <div className="p-4 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expertMode ? (
                  <Beaker className="w-4 h-4 text-primary" />
                ) : (
                  <Zap className="w-4 h-4 text-muted-foreground" />
                )}
                <span className="text-sm font-medium">
                  {expertMode ? "Expert Mode" : "Basic Mode"}
                </span>
              </div>
              <button
                onClick={toggleExpertMode}
                className={cn(
                  "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
                  expertMode ? "bg-primary" : "bg-muted"
                )}
              >
                <span
                  className={cn(
                    "inline-block h-4 w-4 rounded-full bg-white transition-transform",
                    expertMode ? "translate-x-6" : "translate-x-1"
                  )}
                />
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {expertMode
                ? "Full access to 150+ RAG options"
                : "Common options for quick configuration"}
            </p>
          </div>

          {/* Settings content */}
          <div className="p-4">
            {expertMode ? <ExpertSettings /> : <BasicSettings />}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border">
          <button
            onClick={resetSettings}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md hover:bg-muted transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Reset to Defaults
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </>
  )
}
