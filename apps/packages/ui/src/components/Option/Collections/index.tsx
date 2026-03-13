import React, { useEffect } from "react"
import { Empty, Tabs } from "antd"
import { DismissibleBetaAlert } from "@/components/Common/DismissibleBetaAlert"
import type { TabsProps } from "antd"
import { BookOpen, Highlighter, FileText, ArrowLeftRight, CalendarClock, KeyRound, Settings } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useServerOnline } from "@/hooks/useServerOnline"
import { useConnectionUxState } from "@/hooks/useConnectionState"
import { PageShell } from "@/components/Common/PageShell"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useCollectionsStore } from "@/store/collections"
import type { CollectionsTab } from "@/types/collections"
import { ReadingItemsList } from "./ReadingList/ReadingItemsList"
import { HighlightsList } from "./Highlights/HighlightsList"
import { TemplatesList } from "./Templates/TemplatesList"
import { ImportExportPanel } from "./ImportExport/ImportExportPanel"
import { DigestSchedulesPanel } from "./Digests/DigestSchedulesPanel"
import { useNavigate } from "react-router-dom"

/**
 * CollectionsPlaygroundPage
 *
 * Main container for the Collections feature.
 * Provides a tabbed interface for Reading List, Highlights, Templates, and Import/Export.
 */
export const CollectionsPlaygroundPage: React.FC = () => {
  const { t } = useTranslation(["collections", "common"])
  const isOnline = useServerOnline()
  const navigate = useNavigate()
  const { uxState, hasCompletedFirstRun } = useConnectionUxState()

  const activeTab = useCollectionsStore((s) => s.activeTab)
  const setActiveTab = useCollectionsStore((s) => s.setActiveTab)
  const resetStore = useCollectionsStore((s) => s.resetStore)

  // Reset store on unmount — use ref to avoid re-firing if selector returns new reference
  const resetStoreRef = React.useRef(resetStore)
  resetStoreRef.current = resetStore
  useEffect(() => {
    return () => {
      resetStoreRef.current()
    }
  }, [])

  const tabItems: TabsProps["items"] = [
    {
      key: "reading",
      label: (
        <span className="flex items-center gap-2">
          <BookOpen className="h-4 w-4" />
          {t("collections:tabs.reading", "Reading List")}
        </span>
      ),
      children: <ReadingItemsList />
    },
    {
      key: "highlights",
      label: (
        <span className="flex items-center gap-2">
          <Highlighter className="h-4 w-4" />
          {t("collections:tabs.highlights", "Highlights")}
        </span>
      ),
      children: <HighlightsList />
    },
    {
      key: "templates",
      label: (
        <span className="flex items-center gap-2">
          <FileText className="h-4 w-4" />
          {t("collections:tabs.templates", "Templates")}
        </span>
      ),
      children: <TemplatesList />
    },
    {
      key: "digests",
      label: (
        <span className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4" />
          {t("collections:tabs.digests", "Digest Schedules")}
        </span>
      ),
      children: <DigestSchedulesPanel />
    },
    {
      key: "import-export",
      label: (
        <span className="flex items-center gap-2">
          <ArrowLeftRight className="h-4 w-4" />
          {t("collections:tabs.importExport", "Import/Export")}
        </span>
      ),
      children: <ImportExportPanel />
    }
  ]

  const openSettings = () => navigate("/settings/tldw")
  const finishSetup = () => navigate("/")

  if (uxState === "error_auth" || uxState === "configuring_auth") {
    return (
      <PageShell className="py-6" maxWidthClassName="max-w-6xl">
        <FeatureEmptyState
          title={t(
            "collections:authRequiredTitle",
            "Collections needs your credentials before it can load data."
          )}
          description={t(
            "collections:authRequiredDescription",
            "Open Settings to add or repair your tldw server credentials, then come back to Collections."
          )}
          primaryActionLabel={t("collections:openSettings", "Open Settings")}
          onPrimaryAction={openSettings}
          icon={KeyRound}
          iconClassName="h-8 w-8 text-warn"
        />
      </PageShell>
    )
  }

  if (
    uxState === "unconfigured" ||
    uxState === "configuring_url"
  ) {
    const needsFirstRun = !hasCompletedFirstRun
    return (
      <PageShell className="py-6" maxWidthClassName="max-w-6xl">
        <FeatureEmptyState
          title={t(
            "collections:setupRequiredTitle",
            "Finish setup before using Collections."
          )}
          description={t(
            "collections:setupRequiredDescription",
            "Collections depends on your connected tldw server for reading items, templates, and digest schedules."
          )}
          primaryActionLabel={t(
            needsFirstRun
              ? "collections:finishSetup"
              : "collections:openSettings",
            needsFirstRun ? "Finish Setup" : "Open Settings"
          )}
          onPrimaryAction={needsFirstRun ? finishSetup : openSettings}
          icon={Settings}
        />
      </PageShell>
    )
  }

  if (!isOnline || uxState === "error_unreachable") {
    return (
      <PageShell className="py-6" maxWidthClassName="max-w-6xl">
        <Empty
          description={t(
            "collections:offline",
            "Server is offline. Please connect to use Collections."
          )}
        />
      </PageShell>
    )
  }

  return (
    <PageShell className="py-6" maxWidthClassName="max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-text">
          {t("collections:title", "Collections")}
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          {t(
            "collections:description",
            "Save articles, create highlights, manage templates, and import/export your reading list."
          )}
        </p>
      </div>

      <DismissibleBetaAlert
        storageKey="beta-dismissed:collections"
        message={t("collections:betaNotice", "Beta Feature")}
        description={t(
          "collections:betaDescription",
          "Collections is currently in beta. Some features may require backend support."
        )}
        className="mb-6"
      />

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as CollectionsTab)}
        items={tabItems}
        className="collections-tabs"
      />
    </PageShell>
  )
}

export default CollectionsPlaygroundPage
