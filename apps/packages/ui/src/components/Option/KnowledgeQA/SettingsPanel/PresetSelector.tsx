/**
 * PresetSelector - Quick preset selection for RAG settings
 */

import React, { useRef, useCallback, useState } from "react"
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
    color: "text-warn",
  },
  {
    name: "balanced",
    label: "Balanced",
    description: "Hybrid search + reranking",
    icon: Scale,
    color: "text-primary",
  },
  {
    name: "thorough",
    label: "Thorough",
    description: "Deep search + verification",
    icon: Brain,
    color: "text-accent",
  },
  {
    name: "custom",
    label: "Custom",
    description: "Your custom settings",
    icon: Settings,
    color: "text-text-muted",
  },
]

// Additional "Research" preset for advanced users
const RESEARCH_PRESET: PresetConfig = {
  name: "thorough", // Uses thorough as base with modifications
  label: "Research",
  description: "Max verification + citations",
  icon: Beaker,
  color: "text-success",
}

export function PresetSelector() {
  const { preset, setPreset } = useKnowledgeQA()
  const [focusedIndex, setFocusedIndex] = useState(() =>
    PRESETS.findIndex((p) => p.name === preset)
  )
  const gridRef = useRef<HTMLDivElement>(null)
  const buttonRefs = useRef<(HTMLButtonElement | null)[]>([])

  // Handle keyboard navigation in 2x2 grid
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, index: number) => {
      let newIndex = index
      const cols = 2
      const rows = Math.ceil(PRESETS.length / cols)

      switch (e.key) {
        case 'ArrowRight':
          e.preventDefault()
          newIndex = index % cols === cols - 1 ? index - (cols - 1) : index + 1
          break
        case 'ArrowLeft':
          e.preventDefault()
          newIndex = index % cols === 0 ? index + (cols - 1) : index - 1
          break
        case 'ArrowDown':
          e.preventDefault()
          newIndex = index + cols >= PRESETS.length ? index % cols : index + cols
          break
        case 'ArrowUp':
          e.preventDefault()
          newIndex = index - cols < 0 ? (rows - 1) * cols + (index % cols) : index - cols
          // Handle case where bottom row might be partial
          if (newIndex >= PRESETS.length) {
            newIndex = PRESETS.length - 1
          }
          break
        case 'Enter':
        case ' ':
          e.preventDefault()
          setPreset(PRESETS[index].name)
          return
        default:
          return
      }

      // Ensure newIndex is within bounds
      newIndex = Math.max(0, Math.min(newIndex, PRESETS.length - 1))
      setFocusedIndex(newIndex)
      buttonRefs.current[newIndex]?.focus()
    },
    [setPreset]
  )

  return (
    <div className="space-y-3">
      <label id="preset-selector-label" className="text-sm font-medium">Search Preset</label>
      <div
        ref={gridRef}
        role="radiogroup"
        aria-labelledby="preset-selector-label"
        className="grid grid-cols-2 gap-2"
      >
        {PRESETS.map((p, index) => {
          const Icon = p.icon
          const isSelected = preset === p.name
          return (
            <button
              key={p.name}
              ref={(el) => { buttonRefs.current[index] = el }}
              role="radio"
              aria-checked={isSelected}
              tabIndex={focusedIndex === index ? 0 : -1}
              onClick={() => setPreset(p.name)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              onFocus={() => setFocusedIndex(index)}
              className={cn(
                "flex flex-col items-start p-3 rounded-lg border transition-all text-left",
                isSelected
                  ? "border-primary bg-primary/5 ring-1 ring-primary"
                  : "border-border hover:border-primary/30 hover:bg-muted/50",
                "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1"
              )}
            >
              <div className="flex items-center gap-2">
                <Icon className={cn("w-4 h-4", isSelected ? "text-primary" : p.color)} />
                <span className="font-medium text-sm">{p.label}</span>
              </div>
              <p className="text-xs text-text-muted mt-1">
                {p.description}
              </p>
            </button>
          )
        })}
      </div>

      {/* Preset details */}
      <div className="p-3 bg-muted/30 rounded-lg">
        <h4 className="text-xs font-medium uppercase tracking-wide text-text-muted mb-2">
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
    <ul className="text-xs text-text-muted space-y-1">
      {details[preset].map((item, i) => (
        <li key={i} className="flex items-start gap-1.5">
          <span className="text-primary">•</span>
          {item}
        </li>
      ))}
    </ul>
  )
}
