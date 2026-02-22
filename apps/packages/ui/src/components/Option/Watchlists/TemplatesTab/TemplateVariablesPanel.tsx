import React, { useMemo, useState } from "react"
import { Button, Input, Tag } from "antd"
import { TEMPLATE_VARIABLES, CATEGORY_LABELS, CATEGORY_ORDER, type TemplateVariable } from "./template-context-schema"

interface TemplateVariablesPanelProps {
  onInsert: (text: string) => void
}

export const TemplateVariablesPanel: React.FC<TemplateVariablesPanelProps> = ({ onInsert }) => {
  const [search, setSearch] = useState("")
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})

  const filtered = useMemo(() => {
    if (!search.trim()) return TEMPLATE_VARIABLES
    const q = search.toLowerCase()
    return TEMPLATE_VARIABLES.filter(
      (v) =>
        v.key.toLowerCase().includes(q) ||
        v.description.toLowerCase().includes(q)
    )
  }, [search])

  const grouped = useMemo(() => {
    const map: Record<string, TemplateVariable[]> = {}
    for (const v of filtered) {
      ;(map[v.category] ??= []).push(v)
    }
    return map
  }, [filtered])

  const toggleCategory = (cat: string) => {
    setCollapsed((prev) => ({ ...prev, [cat]: !prev[cat] }))
  }

  return (
    <div className="space-y-3">
      <Input
        placeholder="Search variables…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        allowClear
        size="small"
      />
      <div className="max-h-[420px] overflow-auto space-y-2">
        {CATEGORY_ORDER.filter((cat) => grouped[cat]?.length).map((cat) => (
          <div key={cat}>
            <button
              type="button"
              className="flex w-full items-center gap-1 text-xs font-semibold text-text-muted hover:text-text cursor-pointer bg-transparent border-0 p-0"
              onClick={() => toggleCategory(cat)}
            >
              <span>{collapsed[cat] ? "▸" : "▾"}</span>
              <span>{CATEGORY_LABELS[cat] ?? cat}</span>
              <Tag className="ml-1">{grouped[cat].length}</Tag>
            </button>
            {!collapsed[cat] && (
              <div className="ml-3 mt-1 space-y-1">
                {grouped[cat].map((v) => (
                  <div
                    key={v.key}
                    className="flex items-center justify-between gap-2 rounded px-2 py-1 hover:bg-surface text-xs"
                  >
                    <div className="min-w-0 flex-1">
                      <code className="text-primary font-mono text-[11px]">{v.key}</code>
                      <span className="ml-2 text-text-muted">{v.description}</span>
                    </div>
                    <Button
                      size="small"
                      type="link"
                      className="shrink-0 text-[11px]"
                      onClick={() => onInsert(v.insertText)}
                    >
                      Insert
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {Object.keys(grouped).length === 0 && (
          <div className="text-xs text-text-muted p-2">No matching variables found.</div>
        )}
      </div>
    </div>
  )
}

export default TemplateVariablesPanel
