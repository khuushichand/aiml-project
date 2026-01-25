/**
 * PresetSelector - Quick preset selection for RAG settings
 */

import React from "react"
import { Zap, Scale, Brain, Beaker, Settings } from "lucide-react"
import { useKnowledgeQA } from "../KnowledgeQAProvider"
import { cn } from "@/lib/utils"
import type { RagPresetName } from "@/services/rag/unified-rag"

type PresetConfig = {
  name: RagPresetName
  label: string
  description: string
  icon: React.ElementType
  color: string
}

const PRESETS: PresetConfig[] = [
  {
    name: "fast",
    label: "Fast",
    description: "Quick results, FTS only",
    icon: Zap,
    color: "text-yellow-500",
  },
  {
    name: "balanced",
    label: "Balanced",
    description: "Hybrid search + reranking",
    icon: Scale,
    color: "text-blue-500",
  },
  {
    name: "thorough",
    label: "Thorough",
    description: "Deep search + verification",
    icon: Brain,
    color: "text-purple-500",
  },
  {
    name: "custom",
    label: "Custom",
    description: "Your custom settings",
    icon: Settings,
    color: "text-muted-foreground",
  },
]

// Additional "Research" preset for advanced users
const RESEARCH_PRESET: PresetConfig = {
  name: "thorough", // Uses thorough as base with modifications
  label: "Research",
  description: "Max verification + citations",
  icon: Beaker,
  color: "text-green-500",
}

export function PresetSelector() {
  const { preset, setPreset } = useKnowledgeQA()

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium">Search Preset</label>
      <div className="grid grid-cols-2 gap-2">
        {PRESETS.map((p) => {
          const Icon = p.icon
          const isSelected = preset === p.name
          return (
            <button
              key={p.name}
              onClick={() => setPreset(p.name)}
              className={cn(
                "flex flex-col items-start p-3 rounded-lg border transition-all",
                isSelected
                  ? "border-primary bg-primary/5 ring-1 ring-primary"
                  : "border-border hover:border-primary/30 hover:bg-muted/50"
              )}
            >
              <div className="flex items-center gap-2">
                <Icon className={cn("w-4 h-4", isSelected ? "text-primary" : p.color)} />
                <span className="font-medium text-sm">{p.label}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1 text-left">
                {p.description}
              </p>
            </button>
          )
        })}
      </div>

      {/* Preset details */}
      <div className="p-3 bg-muted/30 rounded-lg">
        <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
          {preset === "custom" ? "Custom" : PRESETS.find((p) => p.name === preset)?.label} Settings
        </h4>
        <PresetDetails preset={preset} />
      </div>
    </div>
  )
}

function PresetDetails({ preset }: { preset: RagPresetName }) {
  const details = {
    fast: [
      "Search: Full-text only",
      "Top-K: 5 results",
      "Reranking: Disabled",
      "Max tokens: 300",
    ],
    balanced: [
      "Search: Hybrid (FTS + Vector)",
      "Top-K: 10 results",
      "Reranking: FlashRank",
      "Max tokens: 800",
    ],
    thorough: [
      "Search: Hybrid (0.7 vector weight)",
      "Top-K: 20 results",
      "Reranking: Two-tier",
      "Claims verification: Enabled",
      "Post-verification: Enabled",
    ],
    custom: [
      "Using your custom settings",
      "Modify below to customize",
    ],
  }

  return (
    <ul className="text-xs text-muted-foreground space-y-1">
      {details[preset].map((item, i) => (
        <li key={i} className="flex items-start gap-1.5">
          <span className="text-primary">•</span>
          {item}
        </li>
      ))}
    </ul>
  )
}
