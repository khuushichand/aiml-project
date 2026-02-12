import React from "react"
import { useTranslation } from "react-i18next"
import { MessageSquarePlus, HelpCircle } from "lucide-react"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useDemoMode } from "@/context/demo-mode"
import { useHelpModal } from "@/store/tutorials"

/** Clickable example prompts that populate the composer */
const ExamplePromptChips: React.FC<{
  onSelect: (prompt: string) => void
}> = ({ onSelect }) => {
  const { t } = useTranslation(["playground"])

  const examples = [
    t("playground:empty.clickableExample1", "Summarize the key points from my last uploaded document"),
    t("playground:empty.clickableExample2", "What are the main themes discussed in my notes?"),
    t("playground:empty.clickableExample3", "Help me draft a summary of this conversation")
  ]

  return (
    <div className="flex flex-wrap gap-2 mt-4">
      {examples.map((example, index) => (
        <button
          key={index}
          type="button"
          onClick={() => onSelect(example)}
          className="rounded-xl border border-border/60 bg-surface2/40 px-4 py-2.5 text-sm text-text-muted hover:bg-surface2 hover:text-text hover:border-primary/50 transition-colors"
        >
          {example}
        </button>
      ))}
    </div>
  )
}

export const PlaygroundEmpty = () => {
  const { t } = useTranslation(["playground", "common"])
  const { demoEnabled } = useDemoMode()
  const { open: openHelpModal } = useHelpModal()

  const handleStartChat = React.useCallback(() => {
    window.dispatchEvent(new CustomEvent("tldw:focus-composer"))
  }, [])

  const handleOpenQuickIngest = React.useCallback(() => {
    if (typeof window === "undefined") return
    const trigger = document.querySelector<HTMLButtonElement>(
      '[data-testid="open-quick-ingest"]'
    )
    if (trigger) {
      trigger.click()
      return
    }
    window.dispatchEvent(new CustomEvent("tldw:open-quick-ingest"))
  }, [])

  const handleExampleSelect = React.useCallback((prompt: string) => {
    window.dispatchEvent(
      new CustomEvent("tldw:set-composer-message", { detail: { message: prompt } })
    )
    window.dispatchEvent(new CustomEvent("tldw:focus-composer"))
  }, [])

  return (
    <div className="mx-auto mt-10 max-w-xl px-4">
      <FeatureEmptyState
        icon={MessageSquarePlus}
        title={t("playground:empty.title", {
          defaultValue: "Start a new chat"
        })}
        description={
          demoEnabled
            ? t("playground:empty.demoDescription", {
                defaultValue:
                  "You're in demo mode — try asking a question to see how the assistant responds. You can connect your own tldw server later."
              })
            : t("playground:empty.description", {
                defaultValue:
                  "Experiment with different models, prompts, and knowledge sources here."
              })
        }
        primaryActionLabel={t("playground:empty.primaryCta", {
          defaultValue: "Start chatting"
        })}
        onPrimaryAction={handleStartChat}
        secondaryActionLabel={t("option:header.quickIngest", "Quick Ingest")}
        onSecondaryAction={handleOpenQuickIngest}
        secondaryDisabled={false}
      />

      {/* Example prompts */}
      <div className="mt-6">
        <p className="text-sm font-medium text-text-muted mb-2">
          {t("playground:empty.tryAsking", "Try asking:")}
        </p>
        <ExamplePromptChips onSelect={handleExampleSelect} />

        {/* Take a tour link */}
        <div className="mt-5 text-center">
          <button
            type="button"
            onClick={openHelpModal}
            className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline transition"
          >
            <HelpCircle className="h-3.5 w-3.5" />
            {t("playground:empty.takeTour", "Take a quick tour")}
          </button>
        </div>
      </div>
    </div>
  )
}
