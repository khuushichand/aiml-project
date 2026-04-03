import React from "react"
import { useTranslation } from "react-i18next"
import { Layers } from "lucide-react"
import { Button, Typography } from "antd"
import { browser } from "@/utils/browser-polyfill"

const { Text, Title } = Typography

export default function SidepanelFlashcards() {
  const { t } = useTranslation()

  const openFlashcards = React.useCallback(() => {
    const url = browser.runtime.getURL("/options.html#/flashcards")
    if (browser.tabs?.create) {
      browser.tabs.create({ url }).catch(() => {
        window.open(url, "_blank")
      })
      return
    }
    window.open(url, "_blank")
  }, [])

  React.useEffect(() => {
    openFlashcards()
  }, [openFlashcards])

  return (
    <div className="flex flex-col items-center justify-center gap-4 p-6 text-center">
      <Layers className="size-10 text-text-muted" aria-hidden="true" />
      <Title level={5}>
        {t("sidepanel:flashcards.title", "Flashcards")}
      </Title>
      <Text type="secondary">
        {t(
          "sidepanel:flashcards.openedInTab",
          "Flashcards opens in a full tab for the best study experience."
        )}
      </Text>
      <Button type="primary" onClick={openFlashcards}>
        {t("sidepanel:flashcards.openAgain", "Open Flashcards")}
      </Button>
    </div>
  )
}
