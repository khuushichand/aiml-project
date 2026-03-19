import { AuthShell } from "@web/components/hosted/auth/AuthShell"
import { MagicLinkView } from "@web/components/hosted/auth/MagicLinkView"
import { RoutePlaceholder } from "@web/components/navigation/RoutePlaceholder"
import { isHostedSaaSMode } from "@web/lib/deployment-mode"

export default function MagicLinkPage() {
  if (!isHostedSaaSMode()) {
    return (
      <RoutePlaceholder
        title="Magic Link Sign-In Is Not Active Here"
        description="Self-host deployments keep their auth flow inside the local server and settings surface."
        primaryCtaHref="/login"
        primaryCtaLabel="Open Login"
      />
    )
  }

  return (
    <AuthShell
      title="Confirm your sign-in link"
      description="We’re exchanging the emailed token for a hosted session cookie and sending you straight into the core product."
    >
      <MagicLinkView />
    </AuthShell>
  )
}
