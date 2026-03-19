import { AuthShell } from "@web/components/hosted/auth/AuthShell"
import { SignupForm } from "@web/components/hosted/auth/SignupForm"
import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"
import { isHostedSaaSMode } from "@web/lib/deployment-mode"

export default function SignupPage() {
  if (!isHostedSaaSMode()) {
    return (
      <RoutePlaceholder
        title="Hosted Signup Is Only Available In Managed Mode"
        description="Self-host deployments keep account setup inside the local server configuration flow."
        primaryCtaHref="/login"
        primaryCtaLabel="Open Login"
      />
    )
  }

  return (
    <AuthShell
      title="Create your hosted account"
      description="Start with a single-user subscription flow now. Team controls can follow without changing the basics of signup, verification, and first-run product access."
    >
      <SignupForm />
    </AuthShell>
  )
}
