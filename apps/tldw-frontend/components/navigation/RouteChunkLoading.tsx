type RouteChunkLoadingProps = {
  eyebrow?: string
  title: string
  description: string
  testId?: string
}

export function RouteChunkLoading({
  eyebrow,
  title,
  description,
  testId = "route-chunk-loading"
}: RouteChunkLoadingProps) {
  return (
    <section
      className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-6 py-8"
      data-testid={testId}
    >
      <div className="rounded-3xl border border-border/80 bg-surface/90 p-6 shadow-sm backdrop-blur-sm">
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="mt-2 text-3xl font-semibold text-text">{title}</h1>
        <p className="mt-3 text-sm leading-6 text-text-muted">{description}</p>
      </div>
    </section>
  )
}

export default RouteChunkLoading
