import { Link } from "react-router-dom"

import { useSafeDemoMode } from "@/context/demo-mode"
import { CompanionHomePage } from "./CompanionHomePage"

type CompanionHomeShellProps = {
  surface: "options" | "sidepanel"
  onPersonalizationEnabled?: () => void
}

export function CompanionHomeShell({
  surface,
  onPersonalizationEnabled
}: CompanionHomeShellProps) {
  const { demoEnabled, setDemoEnabled } = useSafeDemoMode()
  const demoExitPath = surface === "sidepanel" ? "/settings" : "/setup"

  const actions =
    surface === "sidepanel"
      ? [
          {
            href: "/?view=chat",
            label: "Open Chat",
            description: "Jump back into the sidepanel chat workspace."
          },
          {
            href: "/settings",
            label: "Open Settings",
            description: "Adjust connection and sidepanel behavior."
          }
        ]
      : [
          {
            href: "/chat",
            label: "Open Chat",
            description: "Continue active work in the main chat workspace."
          },
          {
            href: "/knowledge",
            label: "Open Knowledge",
            description: "Review sources, notes, and captured knowledge from the main workspace."
          },
          {
            href: "/media-multi",
            label: "Open Analysis",
            description: "Review and compare media from the main workspace."
          }
        ]

  return (
    <section
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8"
      data-testid="companion-home-shell"
    >
      {demoEnabled && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text">
                You are in demo mode
              </p>
              <p className="mt-1 text-xs text-text-muted">
                Chat and search use sample data only. Connect a server for full functionality.
              </p>
            </div>
            <Link
              to={demoExitPath}
              onClick={() => setDemoEnabled(false)}
              className="shrink-0 rounded-lg border border-border bg-bg px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-surface-hover"
            >
              Connect a server
            </Link>
          </div>
        </div>
      )}

      <CompanionHomePage
        onPersonalizationEnabled={onPersonalizationEnabled}
        surface={surface}
      />

      <div className="rounded-3xl border border-border/80 bg-surface/90 p-5 shadow-sm backdrop-blur-sm">
        <div>
          <h2 className="text-lg font-semibold text-text">Quick actions</h2>
          <p className="mt-1 text-sm text-text-muted">
            Jump to the main features.
          </p>
        </div>
        <div className="grid gap-3 pt-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="companion-home-quick-actions">
          {actions.map((action) => (
            <Link
              key={action.href}
              to={action.href}
              data-testid={`companion-home-action-${action.href.replace(/\//g, "-").replace(/^-/, "")}`}
              className="rounded-2xl border border-border bg-bg/60 px-4 py-4 transition-colors hover:border-primary/40 hover:bg-primary/5"
            >
              <div className="text-sm font-semibold text-text">{action.label}</div>
              <p className="mt-2 text-sm leading-6 text-text-muted">{action.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}
