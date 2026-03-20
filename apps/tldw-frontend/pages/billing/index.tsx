import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"

export default function BillingPage() {
  return (
    <RoutePlaceholder
      title="Hosted Billing Lives In The Private Distribution"
      description="The OSS web client does not ship the hosted subscription and invoice surface. Self-host deployments should manage commercial billing outside this public frontend."
      primaryCtaHref="/login"
      primaryCtaLabel="Open Login"
    />
  )
}
