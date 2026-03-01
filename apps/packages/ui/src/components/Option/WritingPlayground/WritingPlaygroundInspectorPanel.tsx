import { useRef, type FC, type ReactNode } from "react"
import type { InspectorTabKey } from "./WritingPlayground.types"

type TabDefinition = {
  key: InspectorTabKey
  label: string
  testId: string
}

type WritingPlaygroundInspectorPanelProps = {
  activeTab: InspectorTabKey
  onTabChange: (tab: InspectorTabKey) => void
  generation: ReactNode
  planning: ReactNode
  diagnostics: ReactNode
  tabLabels?: Partial<Record<InspectorTabKey, string>>
}

const TAB_DEFINITIONS: TabDefinition[] = [
  {
    key: "generation",
    label: "Generation",
    testId: "writing-inspector-tab-generation"
  },
  {
    key: "planning",
    label: "Planning",
    testId: "writing-inspector-tab-planning"
  },
  {
    key: "diagnostics",
    label: "Diagnostics",
    testId: "writing-inspector-tab-diagnostics"
  }
]

export const WritingPlaygroundInspectorPanel: FC<
  WritingPlaygroundInspectorPanelProps
> = ({
  activeTab,
  onTabChange,
  generation,
  planning,
  diagnostics,
  tabLabels
}) => {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])

  const selectTabByIndex = (index: number, focus = false) => {
    const normalizedIndex =
      ((index % TAB_DEFINITIONS.length) + TAB_DEFINITIONS.length) %
      TAB_DEFINITIONS.length
    onTabChange(TAB_DEFINITIONS[normalizedIndex].key)
    if (focus) {
      tabRefs.current[normalizedIndex]?.focus()
    }
  }

  const panelMap: Record<InspectorTabKey, ReactNode> = {
    generation,
    planning,
    diagnostics
  }

  return (
    <div data-testid="writing-playground-inspector-panel" className="flex flex-col gap-3">
      <div
        role="tablist"
        aria-label="Writing inspector tabs"
        aria-orientation="horizontal"
        className="inline-flex w-full items-center rounded-md border border-border p-[2px]">
        {TAB_DEFINITIONS.map((tab) => {
          const selected = activeTab === tab.key
          const tabIndex = TAB_DEFINITIONS.findIndex(
            (definition) => definition.key === tab.key
          )
          return (
            <button
              key={tab.key}
              ref={(element) => {
                tabRefs.current[tabIndex] = element
              }}
              id={`writing-inspector-tab-${tab.key}`}
              data-testid={tab.testId}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`writing-inspector-panel-${tab.key}`}
              tabIndex={selected ? 0 : -1}
              className={`flex-1 rounded px-2 py-1 text-xs transition-colors ${
                selected
                  ? "bg-primary text-primary-foreground"
                  : "text-text-secondary hover:bg-surface-hover"
              }`}
              onClick={() => onTabChange(tab.key)}
              onKeyDown={(event) => {
                const currentIndex = TAB_DEFINITIONS.findIndex(
                  (definition) => definition.key === tab.key
                )
                if (event.key === "ArrowRight") {
                  event.preventDefault()
                  selectTabByIndex(currentIndex + 1, true)
                } else if (event.key === "ArrowLeft") {
                  event.preventDefault()
                  selectTabByIndex(currentIndex - 1, true)
                } else if (event.key === "Home") {
                  event.preventDefault()
                  selectTabByIndex(0, true)
                } else if (event.key === "End") {
                  event.preventDefault()
                  selectTabByIndex(TAB_DEFINITIONS.length - 1, true)
                }
              }}>
              {tabLabels?.[tab.key] || tab.label}
            </button>
          )
        })}
      </div>

      {TAB_DEFINITIONS.map((tab) => {
        const selected = activeTab === tab.key
        return (
          <section
            key={tab.key}
            id={`writing-inspector-panel-${tab.key}`}
            role="tabpanel"
            aria-labelledby={`writing-inspector-tab-${tab.key}`}
            hidden={!selected}>
            {selected ? panelMap[tab.key] : null}
          </section>
        )
      })}
    </div>
  )
}
