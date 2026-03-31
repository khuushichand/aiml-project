import { Link } from "react-router-dom"

import { CompanionHomePage } from "./CompanionHomePage"

type CompanionHomeShellProps = {
  surface: "options" | "sidepanel"
  onPersonalizationEnabled?: () => void
}

export function CompanionHomeShell({
  surface,
  onPersonalizationEnabled
}: CompanionHomeShellProps) {
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
      <CompanionHomePage
        onPersonalizationEnabled={onPersonalizationEnabled}
        surface={surface}
      />

      <div className="rounded-3xl border border-border/80 bg-surface/90 p-5 shadow-sm backdrop-blur-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-text">Quick actions</h2>
            <p className="mt-1 text-sm text-text-muted">
              Keep the old escape hatches close while Companion Home grows into the default dashboard.
            </p>
          </div>
          <span className="rounded-full border border-border/70 bg-bg/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
            {surface}
          </span>
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
