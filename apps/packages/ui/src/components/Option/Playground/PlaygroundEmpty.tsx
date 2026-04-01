import React from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"
import {
  MessageSquarePlus,
  HelpCircle,
  Sparkles,
  GitBranch,
  UserCircle2,
  Search,
  Microscope
} from "lucide-react"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useDemoMode } from "@/context/demo-mode"
import { useIsConnected } from "@/hooks/useConnectionState"
import { useHelpModal } from "@/store/tutorials"
import { buildResearchLaunchPath } from "@/routes/route-paths"
import { requestQuickIngestOpen } from "@/utils/quick-ingest-open"

export const PlaygroundEmpty = () => {
  const { t } = useTranslation(["playground", "common"])
  const { demoEnabled } = useDemoMode()
  const isConnected = useIsConnected()
  const { open: openHelpModal } = useHelpModal()
  const navigate = useNavigate()

  const dispatchStarter = React.useCallback(
    (mode: "general" | "compare" | "character" | "rag", prompt?: string) => {
      window.dispatchEvent(
        new CustomEvent("tldw:playground-starter-selected", {
          detail: { mode }
        })
      )
      window.dispatchEvent(
        new CustomEvent("tldw:playground-starter", {
          detail: {
            mode,
            prompt
          }
        })
      )
    },
    []
  )

  const handleStartChat = React.useCallback(() => {
    dispatchStarter("general")
    window.dispatchEvent(new CustomEvent("tldw:focus-composer"))
  }, [dispatchStarter])

  const handleOpenQuickIngest = React.useCallback(() => {
    if (typeof window === "undefined") return
    const trigger = document.querySelector<HTMLButtonElement>(
      '[data-testid="open-quick-ingest"]'
    )
    if (trigger) {
      trigger.click()
      return
    }
    requestQuickIngestOpen()
  }, [])

  const handleOpenHistoryRegion = React.useCallback(() => {
    window.dispatchEvent(new CustomEvent("tldw:open-chat-sidebar"))
  }, [])

  const handleOpenKnowledgeRegion = React.useCallback(() => {
    window.dispatchEvent(
      new CustomEvent("tldw:open-knowledge-panel", {
        detail: { tab: "search" }
      })
    )
  }, [])

  const handleOpenDeepResearch = React.useCallback(() => {
    navigate(buildResearchLaunchPath())
  }, [navigate])

  const starterCards = React.useMemo(
    () => [
      {
        key: "general",
        icon: <Sparkles className="h-4 w-4" />,
        title: t("playground:empty.starterGeneralTitle", "General chat"),
        description: t(
          "playground:empty.starterGeneralBody",
          "Start with a single model and ask anything."
        ),
        action: () => dispatchStarter("general")
      },
      {
        key: "compare",
        icon: <GitBranch className="h-4 w-4" />,
        title: t("playground:empty.starterCompareTitle", "Compare models"),
        description: t(
          "playground:empty.starterCompareBody",
          "Send one prompt to multiple models and pick a winner."
        ),
        action: () => dispatchStarter("compare")
      },
      {
        key: "character",
        icon: <UserCircle2 className="h-4 w-4" />,
        title: t("playground:empty.starterCharacterTitle", "Character chat"),
        description: t(
          "playground:empty.starterCharacterBody",
          "Choose a character and respond in persona."
        ),
        action: () => dispatchStarter("character")
      },
      {
        key: "rag",
        icon: <Search className="h-4 w-4" />,
        title: t("playground:empty.starterKnowledgeTitle", "Knowledge-grounded Q&A"),
        description: t(
          "playground:empty.starterKnowledgeBody",
          "Open Search & Context, pin sources, then ask."
        ),
        action: () => dispatchStarter("rag")
      },
      {
        key: "research",
        icon: <Microscope className="h-4 w-4" />,
        title: t("playground:empty.starterResearchTitle", "Deep Research"),
        description: t(
          "playground:empty.starterResearchBody",
          "Open the long-running research console for cited, checkpointed investigations."
        ),
        action: handleOpenDeepResearch
      }
    ],
    [dispatchStarter, handleOpenDeepResearch, t]
  )

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
            : !isConnected
              ? t("playground:empty.disconnectedDescription", {
                  defaultValue:
                    "Connect to a tldw server to start chatting. Go to Settings to configure your connection."
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
      <div className="mt-6">
        <p className="text-sm font-medium text-text-muted mb-2">
          {t("playground:empty.starterTitle", "Start with a guided mode:")}
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {starterCards.map((starter) => (
            <button
              key={starter.key}
              type="button"
              onClick={starter.action}
              className="rounded-xl border border-border/60 bg-surface2/30 px-3 py-3 text-left transition-colors hover:border-primary/50 hover:bg-surface2"
            >
              <div className="flex items-center gap-2 text-text">
                {starter.icon}
                <span className="text-sm font-medium">{starter.title}</span>
              </div>
              <p className="mt-1 text-xs text-text-muted">{starter.description}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-border bg-surface2/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          {t("playground:empty.layoutGuideTitle", "Page regions")}
        </p>
        <p className="mt-1 text-sm text-text-muted">
          {t(
            "playground:empty.layoutGuideBody",
            "History (left), timeline (center), composer (bottom), Search & Context (right)."
          )}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleOpenHistoryRegion}
            className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-muted transition hover:bg-surface2 hover:text-text"
          >
            {t("playground:empty.jumpHistory", "Open history")}
          </button>
          <button
            type="button"
            onClick={handleStartChat}
            className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-muted transition hover:bg-surface2 hover:text-text"
          >
            {t("playground:empty.jumpComposer", "Jump to composer")}
          </button>
          <button
            type="button"
            onClick={handleOpenKnowledgeRegion}
            className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-muted transition hover:bg-surface2 hover:text-text"
          >
            {t("playground:empty.jumpKnowledge", "Open Search & Context")}
          </button>
        </div>
      </div>

      <div className="mt-6">
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
