import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"

export default function ResetPasswordPage() {
  return (
    <RoutePlaceholder
      title="Password Reset Is Not Active Here"
      description="Hosted password recovery routes live in the private hosted distribution. Self-host deployments manage password recovery through local server configuration."
      primaryCtaHref="/login"
      primaryCtaLabel="Open Login"
    />
  )
}
