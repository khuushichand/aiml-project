import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"

export default function SignupPage() {
  return (
    <RoutePlaceholder
      title="Signup Is Not Part Of The OSS Web Surface"
      description="Hosted account creation now lives in the private hosted distribution. Self-host deployments keep account setup inside the local server configuration flow."
      primaryCtaHref="/login"
      primaryCtaLabel="Open Login"
    />
  )
}
