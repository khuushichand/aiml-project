import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"

export default function AccountPage() {
  return (
    <RoutePlaceholder
      title="Hosted Account Pages Live In The Private Distribution"
      description="The OSS web client does not ship the hosted account surface. Self-host operators can manage users and auth through the local server and admin flows."
      primaryCtaHref="/login"
      primaryCtaLabel="Open Login"
    />
  )
}
