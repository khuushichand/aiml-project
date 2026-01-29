import dynamic from "next/dynamic"

const TldwSettings = dynamic(
  () => import("@/components/Option/Settings/tldw").then((m) => m.TldwSettings),
  { ssr: false }
)

const LoginPage = () => {
  return (
    <div className="min-h-screen bg-bg">
      <div className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <TldwSettings />
      </div>
    </div>
  )
}

export default LoginPage
