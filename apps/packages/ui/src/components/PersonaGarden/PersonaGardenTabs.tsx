import React from "react"
import { useTranslation } from "react-i18next"

export type PersonaGardenTabItem = {
  key: string
  label: string
  content: React.ReactNode
}

type PersonaGardenTabsProps = {
  activeKey: string
  items: PersonaGardenTabItem[]
  onChange: (key: string) => void
}

export const PersonaGardenTabs: React.FC<PersonaGardenTabsProps> = ({
  activeKey,
  items,
  onChange
}) => {
  const { t } = useTranslation(["sidepanel", "common"])

  return (
    <div className="flex flex-1 flex-col gap-3">
      <div
        role="tablist"
        aria-label={t("sidepanel:personaGarden.tabs.ariaLabel", {
          defaultValue: "Persona Garden sections"
        })}
        className="flex flex-wrap gap-2"
      >
        {items.map((item) => {
          const isActive = item.key === activeKey
          const tabId = `persona-garden-tab-${item.key}`
          const panelId = `persona-garden-panel-${item.key}`
          return (
            <button
              key={item.key}
              id={tabId}
              type="button"
              role="tab"
              tabIndex={isActive ? 0 : -1}
              aria-selected={isActive}
              aria-controls={panelId}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                isActive
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-surface text-text-muted hover:bg-surface2 hover:text-text"
              }`}
              onClick={() => onChange(item.key)}
            >
              {item.label}
            </button>
          )
        })}
      </div>
      <div className="flex flex-1 flex-col">
        {items.map((item) => {
          const isActive = item.key === activeKey
          const tabId = `persona-garden-tab-${item.key}`
          const panelId = `persona-garden-panel-${item.key}`
          return (
            <section
              key={item.key}
              id={panelId}
              role="tabpanel"
              aria-labelledby={tabId}
              hidden={!isActive}
              className={isActive ? "flex flex-1 flex-col gap-3" : undefined}
            >
              {item.content}
            </section>
          )
        })}
      </div>
    </div>
  )
}
