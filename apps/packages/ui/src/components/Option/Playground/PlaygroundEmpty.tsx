import React from "react"
import { useTranslation } from "react-i18next"
import { MessageSquarePlus, Mic, Search, GitCompare, HelpCircle } from "lucide-react"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useDemoMode } from "@/context/demo-mode"
import { usePlaygroundTour } from "./PlaygroundTour"

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
          className="rounded-full border border-border/80 bg-surface2/50 px-3 py-1.5 text-xs text-text-muted hover:bg-surface2 hover:text-text hover:border-primary/50 transition-colors"
        >
          {example}
        </button>
      ))}
    </div>
  )
}

/** Feature discovery hints */
const FeatureDiscoveryHints: React.FC = () => {
  const { t } = useTranslation(["playground"])

  const features = [
    {
      icon: Mic,
      label: t("playground:empty.featureVoice", "Voice Chat"),
      hint: t("playground:empty.featureVoiceHint", "Hands-free conversation with audio responses")
    },
    {
      icon: Search,
      label: t("playground:empty.featureSearch", "Knowledge Search"),
      hint: t("playground:empty.featureSearchHint", "Search your ingested media and notes")
    },
    {
      icon: GitCompare,
      label: t("playground:empty.featureCompare", "Compare Mode"),
      hint: t("playground:empty.featureCompareHint", "Send to multiple models at once")
    }
  ]

  return (
    <div className="mt-5 pt-4 border-t border-border/50">
      <p className="text-[11px] font-medium text-text-muted mb-3 uppercase tracking-wider">
        {t("playground:empty.discoverFeatures", "Discover features")}
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {features.map(({ icon: Icon, label, hint }) => (
          <div
            key={label}
            className="flex items-start gap-2 rounded-lg bg-surface2/30 p-2 text-xs"
          >
            <Icon className="h-4 w-4 text-primary/70 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-medium text-text">{label}</span>
              <p className="text-text-muted text-[10px] mt-0.5">{hint}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export const PlaygroundEmpty = () => {
  const { t } = useTranslation(["playground", "common"])
  const { demoEnabled } = useDemoMode()
  const { resetTour } = usePlaygroundTour()

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
    // Dispatch custom event to set the message in the composer and focus it
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
        examples={[
          t("playground:empty.example1", {
            defaultValue:
              "Ask a question, then drag in documents or web pages you want to discuss."
          }),
          t("playground:empty.example2", {
            defaultValue:
              "Use Quick ingest to add transcripts or notes, then reference them in chat."
          }),
          t("playground:empty.example3", {
            defaultValue:
              "Try different prompts or models, or open Model Playground to compare answers."
          })
        ]}
        primaryActionLabel={t("playground:empty.primaryCta", {
          defaultValue: "Start chatting"
        })}
        onPrimaryAction={handleStartChat}
        secondaryActionLabel={t("option:header.quickIngest", "Quick ingest")}
        onSecondaryAction={handleOpenQuickIngest}
        secondaryDisabled={false}
      />

      {/* Clickable example prompts */}
      <div className="mt-6 rounded-2xl border border-border/60 bg-surface/80 p-4 backdrop-blur">
        <p className="text-xs font-medium text-text-muted mb-2">
          {t("playground:empty.tryAsking", "Try asking:")}
        </p>
        <ExamplePromptChips onSelect={handleExampleSelect} />

        {/* Feature discovery hints */}
        <FeatureDiscoveryHints />

        {/* Take a tour link */}
        <div className="mt-4 pt-3 border-t border-border/30 text-center">
          <button
            type="button"
            onClick={resetTour}
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
