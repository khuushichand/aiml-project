import "../styles/globals.css"
import "@web/extension/shims/runtime-bootstrap"
// Use web-specific i18n that works with SSR/static generation
import "@web/lib/i18n-web"
import type { AppProps } from "next/app"
import { AppProviders } from "@web/components/AppProviders"

export default function App({ Component, pageProps }: AppProps) {
  return (
    <AppProviders>
      <Component {...pageProps} />
    </AppProviders>
  )
}
