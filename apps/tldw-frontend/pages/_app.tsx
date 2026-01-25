import "../styles/globals.css"
import "@web/extension/shims/runtime-bootstrap"
// Use web-specific i18n that works with SSR/static generation
import "@web/lib/i18n-web"
import type { AppProps } from "next/app"
import dynamic from "next/dynamic"
import { useRouter } from "next/router"
import { AppProviders } from "@web/components/AppProviders"

const OptionLayout = dynamic(
  () => import("@web/extension/components/Layouts/Layout"),
  { ssr: false }
)

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter()
  const pathname = router.pathname || ""
  const isChatRoute = pathname === "/chat"
  const isLoginRoute = pathname === "/login"
  const isSettingsRoute =
    pathname === "/settings" || pathname.startsWith("/settings/")

  return (
    <AppProviders>
      {isChatRoute || isLoginRoute ? (
        <Component {...pageProps} />
      ) : (
        <OptionLayout
          hideSidebar={isSettingsRoute}
          allowNestedHideHeader={!isSettingsRoute}
        >
          <Component {...pageProps} />
        </OptionLayout>
      )}
    </AppProviders>
  )
}
