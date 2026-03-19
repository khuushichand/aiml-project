import { AuthShell } from "@web/components/hosted/auth/AuthShell"
import { ResetPasswordView } from "@web/components/hosted/auth/ResetPasswordView"
import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"
import { isHostedSaaSMode } from "@web/lib/deployment-mode"

export default function ResetPasswordPage() {
  if (!isHostedSaaSMode()) {
    return (
      <RoutePlaceholder
        title="Password Reset Is Not Active Here"
        description="Self-host deployments manage password recovery through their local server configuration."
        primaryCtaHref="/login"
        primaryCtaLabel="Open Login"
      />
    )
  }

  return (
    <AuthShell
      title="Set a new password"
      description="Password recovery in hosted mode finishes through same-origin auth routes so browser code never needs bearer tokens."
    >
      <ResetPasswordView />
    </AuthShell>
  )
}
