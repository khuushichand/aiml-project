import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"

export default function VerifyEmailPage() {
  return (
    <RoutePlaceholder
      title="Email Verification Is Not Active Here"
      description="Hosted verification routes live in the private hosted distribution. Self-host deployments handle account verification through their local auth configuration."
      primaryCtaHref="/login"
      primaryCtaLabel="Open Login"
    />
  )
}
