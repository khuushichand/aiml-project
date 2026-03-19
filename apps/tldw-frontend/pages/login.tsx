import dynamic from "next/dynamic"
import { AuthShell } from "@web/components/hosted/auth/AuthShell"
import { LoginForm } from "@web/components/hosted/auth/LoginForm"
import { isHostedSaaSMode } from "@web/lib/deployment-mode"

const TldwSettings = dynamic(
  () => import("@/components/Option/Settings/tldw").then((m) => m.TldwSettings),
  { ssr: false }
)

const LoginPage = () => {
  if (isHostedSaaSMode()) {
    return (
      <AuthShell
        title="Sign in"
        description="Hosted tldw keeps the first-run path focused: authenticate, ingest media, ask questions, and search your knowledge without touching backend setup."
      >
        <LoginForm />
      </AuthShell>
    )
  }

  return (
    <div className="min-h-screen bg-bg">
      <div className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <TldwSettings />
      </div>
    </div>
  )
}

export default LoginPage
