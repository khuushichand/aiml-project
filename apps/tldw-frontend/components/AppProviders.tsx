import React, { useEffect, useRef, useState } from "react"
import { App as AntdApp, ConfigProvider, Empty, theme } from "antd"
import { StyleProvider } from "@ant-design/cssinjs"
import { QueryClientProvider } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useDarkMode } from "@/hooks/useDarkmode"
import { PageAssistProvider } from "@/components/Common/PageAssistProvider"
import { FontSizeProvider } from "@/context/FontSizeProvider"
import { DemoModeProvider } from "@/context/demo-mode"
import { getQueryClient } from "@/services/query-client"

type AppProvidersProps = {
  children: React.ReactNode
}

const queryClient = getQueryClient()
const EMPTY_STYLES = { image: { height: 60 } }

export const AppProviders: React.FC<AppProvidersProps> = ({ children }) => {
  const { mode } = useDarkMode()
  const { i18n, t } = useTranslation("common")
  // SSR-safe: default to "ltr", update on client
  const [direction, setDirection] = useState<"ltr" | "rtl">("ltr")
  const portalRootRef = useRef<HTMLDivElement | null>(null)
  const renderEmpty = React.useCallback(
    () => (
      <Empty
        styles={EMPTY_STYLES}
        description={t("noData", { defaultValue: "No data" })}
      />
    ),
    [t]
  )

  const getPopupContainer = React.useCallback(
    (triggerNode?: HTMLElement) => {
      if (typeof document === "undefined") {
        return (triggerNode ?? ({} as HTMLElement))
      }
      return portalRootRef.current ?? triggerNode ?? document.body
    },
    []
  )

  useEffect(() => {
    if (typeof document === "undefined") return
    const language = i18n.resolvedLanguage || i18n.language
    document.documentElement.lang = language
    document.documentElement.dir = i18n.dir(language)
    setDirection(i18n.dir(language))
  }, [i18n, i18n.resolvedLanguage, i18n.language])

  return (
    <StyleProvider hashPriority="high">
      <QueryClientProvider client={queryClient}>
        <DemoModeProvider>
          <PageAssistProvider>
            <FontSizeProvider>
              <ConfigProvider
                theme={{
                  algorithm:
                    mode === "dark"
                      ? theme.darkAlgorithm
                      : theme.defaultAlgorithm,
                  token: {
                    fontFamily: "Arimo"
                  }
                }}
                getPopupContainer={getPopupContainer}
                renderEmpty={renderEmpty}
                direction={direction}
              >
                <AntdApp>{children}</AntdApp>
                <div id="tldw-portal-root" ref={portalRootRef} />
              </ConfigProvider>
            </FontSizeProvider>
          </PageAssistProvider>
        </DemoModeProvider>
      </QueryClientProvider>
    </StyleProvider>
  )
}
