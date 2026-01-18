import React, { useEffect, useRef, useState } from "react"
import { App as AntdApp, ConfigProvider, Empty, theme } from "antd"
import { StyleProvider } from "@ant-design/cssinjs"
import { QueryClientProvider } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useDarkMode } from "@/hooks/useDarkmode"
import { PageAssistProvider } from "@/components/Common/PageAssistProvider"
import { FontSizeProvider } from "@/context/FontSizeProvider"
import { getQueryClient } from "@/services/query-client"

type AppProvidersProps = {
  children: React.ReactNode
}

const queryClient = getQueryClient()

export const AppProviders: React.FC<AppProvidersProps> = ({ children }) => {
  const { mode } = useDarkMode()
  const { i18n } = useTranslation()
  const [direction, setDirection] = useState<"ltr" | "rtl">("ltr")
  const portalRootRef = useRef<HTMLDivElement | null>(null)

  const getPopupContainer = React.useCallback(() => {
    if (typeof document === "undefined") return undefined
    return portalRootRef.current ?? document.body
  }, [])

  useEffect(() => {
    if (typeof document === "undefined") return
    if (!i18n.resolvedLanguage) return
    document.documentElement.lang = i18n.resolvedLanguage
    document.documentElement.dir = i18n.dir(i18n.resolvedLanguage)
    setDirection(i18n.dir(i18n.resolvedLanguage))
  }, [i18n, i18n.resolvedLanguage])

  return (
    <StyleProvider hashPriority="high">
      <QueryClientProvider client={queryClient}>
        <PageAssistProvider>
          <FontSizeProvider>
            <ConfigProvider
              theme={{
                algorithm:
                  mode === "dark" ? theme.darkAlgorithm : theme.defaultAlgorithm,
                token: {
                  fontFamily: "Arimo"
                }
              }}
              getPopupContainer={getPopupContainer}
              renderEmpty={() => (
                <Empty
                  styles={{ image: { height: 60 } }}
                  description="No data"
                />
              )}
              direction={direction}
            >
              <AntdApp>{children}</AntdApp>
              <div id="tldw-portal-root" ref={portalRootRef} />
            </ConfigProvider>
          </FontSizeProvider>
        </PageAssistProvider>
      </QueryClientProvider>
    </StyleProvider>
  )
}
