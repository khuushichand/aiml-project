import Link from "next/link"

export default function BillingCancelPage() {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-3xl items-center px-4 py-8 sm:px-6 lg:px-8">
      <div className="w-full rounded-[2rem] border border-border/70 bg-bg/95 p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          Billing canceled
        </p>
        <h1 className="mt-3 font-serif text-4xl text-text">Checkout was canceled</h1>
        <p className="mt-4 text-sm leading-6 text-text-muted">
          No subscription change was applied. You can review the available plans again or return to the product without leaving the hosted customer surface.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/billing"
            className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primaryStrong"
          >
            Return to billing
          </Link>
          <Link
            href="/chat"
            className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text transition-colors hover:bg-surface2"
          >
            Continue to chat
          </Link>
        </div>
      </div>
    </div>
  )
}
