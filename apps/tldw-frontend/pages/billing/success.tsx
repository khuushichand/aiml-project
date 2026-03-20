import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"

export default function BillingSuccessPage() {
  return (
    <RoutePlaceholder
      title="Hosted Billing Redirects Live In The Private Distribution"
      description="The hosted checkout success route is not part of the OSS web client."
      primaryCtaHref="/login"
      primaryCtaLabel="Open Login"
    />
  )
}
