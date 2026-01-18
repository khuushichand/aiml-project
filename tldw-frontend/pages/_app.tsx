import "../styles/globals.css"
import "@/shims/runtime-bootstrap"
import "@/i18n"
import type { AppProps } from "next/app"
import { AppProviders } from "@/app/AppProviders"

export default function App({ Component, pageProps }: AppProps) {
  return (
    <AppProviders>
      <Component {...pageProps} />
    </AppProviders>
  )
}
