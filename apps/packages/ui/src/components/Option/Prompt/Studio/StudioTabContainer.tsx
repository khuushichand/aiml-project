import { Segmented, Badge } from "antd"
import {
  FolderKanban,
  FileText,
  TestTube,
  BarChart3,
  Sparkles,
  Activity
} from "lucide-react"
import React, { useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  usePromptStudioStore,
  type StudioSubTab
} from "@/store/prompt-studio"
import { hasPromptStudio, getPromptStudioStatus } from "@/services/prompt-studio"
import { useServerOnline } from "@/hooks/useServerOnline"
import ConnectFeatureBanner from "@/components/Common/ConnectFeatureBanner"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { QueueHealthWidget } from "./QueueHealthWidget"
import { ProjectsTab } from "./Projects/ProjectsTab"
import { StudioPromptsTab } from "./Prompts/StudioPromptsTab"
import { TestCasesTab } from "./TestCases/TestCasesTab"
import { EvaluationsTab } from "./Evaluations/EvaluationsTab"
import { OptimizationsTab } from "./Optimizations/OptimizationsTab"

const SUB_TAB_OPTIONS: StudioSubTab[] = [
  "projects",
  "prompts",
  "testCases",
  "evaluations",
  "optimizations"
]

const isValidSubTab = (tab: string | null): tab is StudioSubTab =>
  tab !== null && SUB_TAB_OPTIONS.includes(tab as StudioSubTab)

export const StudioTabContainer: React.FC = () => {
  const { t } = useTranslation(["settings", "common", "option"])
  const [searchParams, setSearchParams] = useSearchParams()
  const isOnline = useServerOnline()

  const activeSubTab = usePromptStudioStore((s) => s.activeSubTab)
  const setActiveSubTab = usePromptStudioStore((s) => s.setActiveSubTab)
  const selectedProjectId = usePromptStudioStore((s) => s.selectedProjectId)

  // Capability check
  const { data: hasStudio, isLoading: isCheckingCapability } = useQuery({
    queryKey: ["prompt-studio", "capability"],
    queryFn: hasPromptStudio,
    enabled: isOnline
  })

  // Queue health status
  const { data: statusResponse } = useQuery({
    queryKey: ["prompt-studio", "status"],
    queryFn: () => getPromptStudioStatus(),
    enabled: isOnline && hasStudio === true,
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  const status = (statusResponse as any)?.data?.data

  // Sync URL with active sub-tab
  useEffect(() => {
    const subtabParam = searchParams.get("subtab")
    if (isValidSubTab(subtabParam) && subtabParam !== activeSubTab) {
      setActiveSubTab(subtabParam)
    }
  }, [searchParams, activeSubTab, setActiveSubTab])

  // Update URL when sub-tab changes
  useEffect(() => {
    const currentSubtab = searchParams.get("subtab")
    if (currentSubtab !== activeSubTab) {
      const newParams = new URLSearchParams(searchParams)
      newParams.set("subtab", activeSubTab)
      setSearchParams(newParams, { replace: true })
    }
  }, [activeSubTab, searchParams, setSearchParams])

  const handleSubTabChange = (value: string | number) => {
    if (isValidSubTab(value as string)) {
      setActiveSubTab(value as StudioSubTab)
    }
  }

  // Offline state
  if (!isOnline) {
    return (
      <ConnectFeatureBanner
        title={t("settings:managePrompts.studio.connectTitle", {
          defaultValue: "Connect to use Prompt Studio"
        })}
        description={t("settings:managePrompts.studio.connectDescription", {
          defaultValue:
            "To access full Prompt Studio features, connect to your tldw server first."
        })}
        examples={[
          t("settings:managePrompts.studio.connectExample1", {
            defaultValue: "Open Settings -> tldw server to add your server URL."
          }),
          t("settings:managePrompts.studio.connectExample2", {
            defaultValue:
              "Once connected, you can manage projects, prompts, test cases, evaluations, and optimizations."
          })
        ]}
      />
    )
  }

  // Loading capability check
  if (isCheckingCapability) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-pulse text-text-muted">
          {t("common:loading.title", { defaultValue: "Loading..." })}
        </div>
      </div>
    )
  }

  // Prompt Studio not available
  if (hasStudio === false) {
    return (
      <FeatureEmptyState
        title={t("managePrompts.studio.unavailableTitle", {
          defaultValue: "Prompt Studio not available"
        })}
        description={t("managePrompts.studio.unavailableDescription", {
          defaultValue:
            "Your server doesn't have Prompt Studio enabled, or you don't have permission to access it."
        })}
        examples={[
          t("managePrompts.studio.unavailableExample1", {
            defaultValue:
              "Contact your server administrator to enable Prompt Studio."
          }),
          t("managePrompts.studio.unavailableExample2", {
            defaultValue:
              "You can still create and manage prompts locally in the Custom tab."
          })
        ]}
      />
    )
  }

  const segmentedOptions = [
    {
      value: "projects",
      label: (
        <span className="flex items-center gap-1.5">
          <FolderKanban className="size-4" />
          <span className="hidden sm:inline">
            {t("managePrompts.studio.tabs.projects", { defaultValue: "Projects" })}
          </span>
        </span>
      )
    },
    {
      value: "prompts",
      label: (
        <span className="flex items-center gap-1.5">
          <FileText className="size-4" />
          <span className="hidden sm:inline">
            {t("managePrompts.studio.tabs.prompts", { defaultValue: "Prompts" })}
          </span>
        </span>
      ),
      disabled: !selectedProjectId
    },
    {
      value: "testCases",
      label: (
        <span className="flex items-center gap-1.5">
          <TestTube className="size-4" />
          <span className="hidden sm:inline">
            {t("managePrompts.studio.tabs.testCases", { defaultValue: "Test Cases" })}
          </span>
        </span>
      ),
      disabled: !selectedProjectId
    },
    {
      value: "evaluations",
      label: (
        <span className="flex items-center gap-1.5">
          <BarChart3 className="size-4" />
          <span className="hidden sm:inline">
            {t("managePrompts.studio.tabs.evaluations", { defaultValue: "Evaluations" })}
          </span>
          {status?.processing > 0 && (
            <Badge
              count={status.processing}
              size="small"
              style={{ backgroundColor: "rgb(var(--color-success))" }}
            />
          )}
        </span>
      ),
      disabled: !selectedProjectId
    },
    {
      value: "optimizations",
      label: (
        <span className="flex items-center gap-1.5">
          <Sparkles className="size-4" />
          <span className="hidden sm:inline">
            {t("managePrompts.studio.tabs.optimizations", {
              defaultValue: "Optimizations"
            })}
          </span>
        </span>
      ),
      disabled: !selectedProjectId
    }
  ]

  const renderContent = () => {
    switch (activeSubTab) {
      case "projects":
        return <ProjectsTab />
      case "prompts":
        return <StudioPromptsTab />
      case "testCases":
        return <TestCasesTab />
      case "evaluations":
        return <EvaluationsTab />
      case "optimizations":
        return <OptimizationsTab />
      default:
        return <ProjectsTab />
    }
  }

  return (
    <div className="space-y-4" data-testid="studio-tab-container">
      {/* Header with sub-tabs and status */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Segmented
          value={activeSubTab}
          onChange={handleSubTabChange}
          options={segmentedOptions}
          data-testid="studio-subtab-selector"
        />

        <QueueHealthWidget status={status} />
      </div>

      {/* Project context reminder for non-project tabs */}
      {activeSubTab !== "projects" && !selectedProjectId && (
        <div className="p-4 bg-warn/10 border border-warn/30 rounded-md">
          <p className="text-sm text-warn">
            {t("managePrompts.studio.selectProjectFirst", {
              defaultValue:
                "Please select a project in the Projects tab to access this feature."
            })}
          </p>
        </div>
      )}

      {/* Content area */}
      <div className="min-h-[400px]">{renderContent()}</div>
    </div>
  )
}
