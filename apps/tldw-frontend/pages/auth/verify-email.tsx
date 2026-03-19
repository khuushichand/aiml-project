import { AuthShell } from "@web/components/hosted/auth/AuthShell"
import { VerifyEmailView } from "@web/components/hosted/auth/VerifyEmailView"
import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"
import { isHostedSaaSMode } from "@web/lib/deployment-mode"

export default function VerifyEmailPage() {
  if (!isHostedSaaSMode()) {
    return (
      <RoutePlaceholder
        title="Email Verification Is Not Active Here"
        description="Self-host deployments handle account verification through their own local auth configuration."
        primaryCtaHref="/login"
        primaryCtaLabel="Open Login"
      />
    )
  }

  return (
    <AuthShell
      title="Verify your email"
      description="We’re finalizing your hosted account so the rest of the product can rely on a clean, server-managed auth session."
    >
      <VerifyEmailView />
    </AuthShell>
  )
}
