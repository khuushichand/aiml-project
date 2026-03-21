import {
  moveCompanionHomeCard,
  setCompanionHomeCardVisibility,
  type CompanionHomeLayoutCard
} from "@/store/companion-home-layout"

type CustomizeHomeDrawerProps = {
  open: boolean
  layout: CompanionHomeLayoutCard[]
  onClose: () => void
  onLayoutChange: (nextLayout: CompanionHomeLayoutCard[]) => void
}

export function CustomizeHomeDrawer({
  open,
  layout,
  onClose,
  onLayoutChange
}: CustomizeHomeDrawerProps) {
  if (!open) {
    return null
  }

  return (
    <div
      aria-labelledby="customize-home-drawer-title"
      aria-modal="true"
      className="fixed inset-0 z-50"
      role="dialog"
    >
      <button
        aria-label="Close customize home"
        className="absolute inset-0 h-full w-full cursor-default bg-slate-950/35"
        onClick={onClose}
        type="button"
      />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-border/80 bg-surface shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-border/70 px-5 py-4">
          <div>
            <h2
              className="text-lg font-semibold text-text"
              id="customize-home-drawer-title"
            >
              Customize Home
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              Keep system cards fixed, then hide or reorder the rest for this
              surface.
            </p>
          </div>
          <button
            className="rounded-full border border-border bg-bg/70 px-3 py-1 text-sm font-medium text-text transition-colors hover:border-primary/40 hover:bg-primary/5"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {layout.map((card, index) => {
            const previousMovable = layout
              .slice(0, index)
              .some((entry) => !entry.fixed)
            const nextMovable = layout
              .slice(index + 1)
              .some((entry) => !entry.fixed)

            return (
              <div
                key={card.id}
                className="rounded-2xl border border-border/70 bg-bg/60 px-4 py-4"
                data-testid={`companion-home-layout-row-${card.id}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-text">{card.title}</div>
                    <p className="mt-1 text-sm text-text-muted">
                      {card.fixed
                        ? "Always shown"
                        : card.visible
                          ? "Shown on this surface"
                          : "Hidden on this surface"}
                    </p>
                  </div>
                  <span className="rounded-full border border-border/70 bg-surface px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                    {card.fixed ? "System" : "Custom"}
                  </span>
                </div>

                {!card.fixed ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      aria-label={`${card.visible ? "Hide" : "Show"} ${card.title}`}
                      className="rounded-full border border-border bg-surface px-3 py-1.5 text-sm font-medium text-text transition-colors hover:border-primary/40 hover:bg-primary/5"
                      onClick={() =>
                        onLayoutChange(
                          setCompanionHomeCardVisibility(layout, card.id, !card.visible)
                        )
                      }
                      type="button"
                    >
                      {card.visible ? "Hide" : "Show"}
                    </button>
                    <button
                      aria-label={`Move ${card.title} up`}
                      className="rounded-full border border-border bg-surface px-3 py-1.5 text-sm font-medium text-text transition-colors hover:border-primary/40 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!previousMovable}
                      onClick={() =>
                        onLayoutChange(moveCompanionHomeCard(layout, card.id, "up"))
                      }
                      type="button"
                    >
                      Move up
                    </button>
                    <button
                      aria-label={`Move ${card.title} down`}
                      className="rounded-full border border-border bg-surface px-3 py-1.5 text-sm font-medium text-text transition-colors hover:border-primary/40 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!nextMovable}
                      onClick={() =>
                        onLayoutChange(moveCompanionHomeCard(layout, card.id, "down"))
                      }
                      type="button"
                    >
                      Move down
                    </button>
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      </aside>
    </div>
  )
}
