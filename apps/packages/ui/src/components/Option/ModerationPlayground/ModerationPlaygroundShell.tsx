import React from "react"
import { useTranslation } from "react-i18next"
import { message } from "antd"
import { useServerOnline } from "@/hooks/useServerOnline"
import { testModeration } from "@/services/moderation"
import { ModerationContextBar } from "./ModerationContextBar"
import { useModerationContext } from "./hooks/useModerationContext"
import { useModerationSettings } from "./hooks/useModerationSettings"
import { useBlocklist } from "./hooks/useBlocklist"
import { useUserOverrides } from "./hooks/useUserOverrides"
import { useModerationTest } from "./hooks/useModerationTest"
import { ONBOARDING_KEY, getErrorStatus } from "./moderation-utils"

// Lazy panel imports — replace with real components in Tasks 5-9
const PolicySettingsPanel = React.lazy(() => import("./PolicySettingsPanel"))
const BlocklistStudioPanel = React.lazy(() => import("./BlocklistStudioPanel"))
const UserOverridesPanel = React.lazy(() => import("./UserOverridesPanel"))
const TestSandboxPanel = React.lazy(() => import("./TestSandboxPanel"))
const AdvancedPanel = React.lazy(() => import("./AdvancedPanel"))

const TABS = [
  { key: "policy", label: "Policy & Settings" },
  { key: "blocklist", label: "Blocklist Studio" },
  { key: "overrides", label: "User Overrides" },
  { key: "test", label: "Test Sandbox" },
  { key: "advanced", label: "Advanced" }
] as const

type TabKey = (typeof TABS)[number]["key"]

const HERO_STYLE: React.CSSProperties = {
  background:
    "linear-gradient(180deg, var(--moderation-hero-start) 0%, var(--moderation-hero-end) 100%)",
  border: "1px solid var(--moderation-hero-border)",
  boxShadow: "0 24px 70px var(--moderation-hero-shadow)"
}
const HERO_GRID_STYLE: React.CSSProperties = {
  backgroundImage:
    "linear-gradient(var(--moderation-hero-grid-1) 1px, transparent 1px), linear-gradient(90deg, var(--moderation-hero-grid-2) 1px, transparent 1px)",
  backgroundSize: "28px 28px",
  opacity: "var(--moderation-hero-grid-opacity)"
}

export const ModerationPlaygroundShell: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const online = useServerOnline()
  const [messageApi, contextHolder] = message.useMessage()
  const [activeTab, setActiveTab] = React.useState<TabKey>("policy")

  const ctx = useModerationContext()
  const settings = useModerationSettings(ctx.activeUserId)
  const blocklist = useBlocklist()
  const overrides = useUserOverrides(ctx.activeUserId)
  const tester = useModerationTest()

  const policy = settings.policyQuery.data || {}
  const hasUnsavedChanges = settings.isDirty || overrides.isDirty || blocklist.isDirtyRaw

  // Authorization check — show error if backend returns 401/403
  const hasPermissionError = [settings.settingsQuery?.error, settings.policyQuery?.error, overrides.overridesQuery?.error]
    .map(getErrorStatus)
    .some((status) => status === 401 || status === 403)

  const [showOnboarding, setShowOnboarding] = React.useState(() => {
    if (typeof window === "undefined") return false
    return !localStorage.getItem(ONBOARDING_KEY)
  })
  const dismissOnboarding = () => {
    setShowOnboarding(false)
    if (typeof window !== "undefined") localStorage.setItem(ONBOARDING_KEY, "true")
  }

  // Ctrl+S save shortcut
  React.useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault()
        if (settings.isDirty)
          void settings
            .save()
            .then(() => messageApi.success("Settings saved"))
            .catch((err: any) => messageApi.error(err?.message || "Save failed"))
        if (overrides.isDirty)
          void overrides
            .save()
            .then(() => messageApi.success("Override saved"))
            .catch((err: any) => messageApi.error(err?.message || "Save failed"))
      }
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [settings, overrides, messageApi])

  // beforeunload warning
  React.useEffect(() => {
    if (!hasUnsavedChanges) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [hasUnsavedChanges])

  // Sync test userId from context — always track active user
  React.useEffect(() => {
    tester.setUserId(ctx.activeUserId ?? "")
  }, [ctx.activeUserId]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleReload = async () => {
    try {
      await settings.reload()
      messageApi.success("Reloaded moderation config")
    } catch (err: any) {
      messageApi.error(err?.message || "Reload failed")
    }
  }

  const handleQuickTest = async (text: string, phase: "input" | "output") => {
    try {
      return await testModeration({
        user_id: ctx.activeUserId || undefined,
        phase,
        text
      })
    } catch (err: any) {
      messageApi.error(err?.message || "Test failed")
      return undefined
    }
  }

  const renderPanel = () => {
    switch (activeTab) {
      case "policy":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <PolicySettingsPanel settings={settings} messageApi={messageApi} />
          </React.Suspense>
        )
      case "blocklist":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <BlocklistStudioPanel blocklist={blocklist} messageApi={messageApi} />
          </React.Suspense>
        )
      case "overrides":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <UserOverridesPanel ctx={ctx} overrides={overrides} messageApi={messageApi} />
          </React.Suspense>
        )
      case "test":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <TestSandboxPanel tester={tester} messageApi={messageApi} />
          </React.Suspense>
        )
      case "advanced":
        return (
          <React.Suspense fallback={<div className="py-8 text-center text-text-muted">Loading...</div>}>
            <AdvancedPanel
              settings={settings}
              blocklist={blocklist}
              overrides={overrides}
              messageApi={messageApi}
            />
          </React.Suspense>
        )
    }
  }

  return (
    <div className="space-y-0">
      {contextHolder}

      {/* Authorization gate — block UI if 401/403 */}
      {hasPermissionError && (
        <div className="mx-4 sm:mx-6 lg:mx-8 mt-4 p-4 border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 rounded-lg">
          <p className="text-sm font-semibold text-red-800 dark:text-red-300">Admin moderation access required</p>
          <p className="text-sm text-red-700 dark:text-red-400 mt-1">
            Moderation controls require an admin account with SYSTEM_CONFIGURE permission.
          </p>
        </div>
      )}

      {!hasPermissionError && <>
      {/* Onboarding */}
      {showOnboarding && (
        <div className="mx-4 sm:mx-6 lg:mx-8 mb-4 p-4 border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <p className="text-sm font-medium">Welcome to Moderation Playground</p>
          <p className="text-sm text-text-muted mt-1">
            Configure content safety rules, test them live, and manage per-user overrides.
          </p>
          <button
            type="button"
            onClick={dismissOnboarding}
            className="text-sm text-blue-600 hover:underline mt-2"
          >
            Got it, let&apos;s start
          </button>
        </div>
      )}

      {/* Hero */}
      <div
        className="relative overflow-hidden rounded-[28px] mx-4 sm:mx-6 lg:mx-8 p-6 sm:p-8 text-text"
        style={HERO_STYLE}
      >
        <div className="absolute inset-0" style={HERO_GRID_STYLE} />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl sm:text-2xl font-display font-bold">
              {t("option:moderationPlayground.title", "Moderation Playground")}
            </h2>
            <p className="text-text-muted text-sm mt-1">
              {t(
                "option:moderationPlayground.subtitle",
                "Family safety controls and server guardrails in one place."
              )}
            </p>
            <div className="mt-2">
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                  online
                    ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                    : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                }`}
              >
                {online ? "Server online" : "Server offline"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Context bar */}
      <ModerationContextBar
        scope={ctx.scope}
        onScopeChange={ctx.setScope}
        userIdDraft={ctx.userIdDraft}
        onUserIdDraftChange={ctx.setUserIdDraft}
        onLoadUser={ctx.loadUser}
        activeUserId={ctx.activeUserId}
        onClearUser={ctx.clearUser}
        userLoading={overrides.loading}
        policy={policy}
        hasUnsavedChanges={hasUnsavedChanges}
        onReload={handleReload}
        onRunQuickTest={handleQuickTest}
        onOpenTestTab={() => setActiveTab("test")}
      />

      {/* Offline warning */}
      {!online && (
        <div className="mx-4 sm:mx-6 lg:mx-8 p-3 border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-sm text-yellow-800 dark:text-yellow-300">
          Connect to your tldw server to use moderation controls.
        </div>
      )}

      {/* Tab bar */}
      <div className="border-b border-border mx-4 sm:mx-6 lg:mx-8">
        <div className="flex overflow-x-auto -mb-px" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`
                px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors
                ${
                  activeTab === tab.key
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-text-muted hover:text-text hover:border-gray-300"
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="mx-4 sm:mx-6 lg:mx-8 py-6">{renderPanel()}</div>
      </>}
    </div>
  )
}
