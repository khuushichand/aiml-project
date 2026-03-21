import { Link } from "react-router-dom"

import type { CompanionHomeItem } from "@/services/companion-home"

export type CompanionHomeCardState = {
  label: string
  description: string
}

type CompanionHomeCardShellProps = {
  title: string
  items: CompanionHomeItem[]
  emptyLabel: string
  emptyDescription: string
  state?: CompanionHomeCardState
  maxItems?: number
}

const formatUpdatedAt = (value: string | null | undefined): string => {
  if (!value) return "Updated recently"
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return "Updated recently"
  return `Updated ${new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric"
  }).format(new Date(timestamp))}`
}

export function CompanionHomeCardShell({
  title,
  items,
  emptyLabel,
  emptyDescription,
  state,
  maxItems = 4
}: CompanionHomeCardShellProps) {
  const visibleItems = items.slice(0, maxItems)
  const subtitle =
    items.length > 0
      ? `${items.length} item${items.length === 1 ? "" : "s"}`
      : state?.label ?? "Nothing urgent right now."

  return (
    <section className="rounded-3xl border border-border/80 bg-surface/90 p-5 shadow-sm backdrop-blur-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-text">{title}</h2>
          <p className="mt-1 text-sm text-text-muted">{subtitle}</p>
        </div>
        <span className="rounded-full border border-border/70 bg-bg/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
          {items.length}
        </span>
      </div>

      {visibleItems.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {visibleItems.map((item) => {
            const content = (
              <>
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-semibold text-text">{item.title}</div>
                  <span className="shrink-0 text-xs text-text-muted">
                    {formatUpdatedAt(item.updatedAt)}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-text-muted">{item.summary}</p>
              </>
            )

            return (
              <li
                key={item.id}
                className="rounded-2xl border border-border/70 bg-bg/60 p-3"
              >
                {item.href ? (
                  <Link className="block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-focus" to={item.href}>
                    {content}
                  </Link>
                ) : (
                  content
                )}
              </li>
            )
          })}
        </ul>
      ) : state ? (
        <div className="mt-4 rounded-2xl border border-dashed border-border/70 bg-bg/60 p-4">
          <div className="text-sm font-semibold text-text">{state.label}</div>
          <p className="mt-2 text-sm leading-6 text-text-muted">{state.description}</p>
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-border/70 bg-bg/60 p-4">
          <div className="text-sm font-semibold text-text">{emptyLabel}</div>
          <p className="mt-2 text-sm leading-6 text-text-muted">{emptyDescription}</p>
        </div>
      )}
    </section>
  )
}
