import "../styles/globals.css"
// react-pdf text/annotation layer styles for Document Workspace
import "react-pdf/dist/esm/Page/AnnotationLayer.css"
import "react-pdf/dist/esm/Page/TextLayer.css"
import "@web/extension/shims/runtime-bootstrap"
// Use web-specific i18n that works with SSR/static generation
import "@web/lib/i18n-web"
import type { AppProps } from "next/app"
import dynamic from "next/dynamic"
import { useRouter } from "next/router"
import React from "react"
import { AppProviders } from "@web/components/AppProviders"

const OptionLayout = dynamic(
  () => import("@web/components/layout/WebLayout"),
  { ssr: false }
)

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter()
  const pathname = router.pathname || ""
  const routePath =
    pathname.length > 1 && pathname.endsWith("/")
      ? pathname.slice(0, -1)
      : pathname

  const isLoginRoute = routePath === "/login"
  const isSettingsRoute =
    routePath === "/settings" || routePath.startsWith("/settings/")

  return (
    <AppProviders>
      {isLoginRoute ? (
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
