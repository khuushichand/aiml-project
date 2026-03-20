import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"

export default function MagicLinkPage() {
  return (
    <RoutePlaceholder
      title="Magic Link Sign-In Is Not Active Here"
      description="Hosted magic-link routes live in the private hosted distribution. Self-host deployments keep auth inside the local server and settings surface."
      primaryCtaHref="/login"
      primaryCtaLabel="Open Login"
    />
  )
}
