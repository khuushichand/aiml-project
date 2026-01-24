import { PageAssistContext } from "@/context"
import { useStoreMessageOption } from "@/store/option"
import React from "react"

// Note: messages state has been moved to useStoreMessageOption (Zustand store)
// This provider now only manages abort controllers for streaming requests
export const PageAssistProvider = ({
  children
}: {
  children: React.ReactNode
}) => {
  const [controller, setController] = React.useState<AbortController | null>(
    null
  )
  const [embeddingController, setEmbeddingController] =
    React.useState<AbortController | null>(null)

  React.useEffect(() => {
    if (typeof window === "undefined") return
    if (process.env.NODE_ENV !== "development") return

    type PageAssistDebug = {
      setMessages: ReturnType<typeof useStoreMessageOption.getState>["setMessages"]
      getMessages: () => ReturnType<typeof useStoreMessageOption.getState>["messages"]
    }
    const w = window as Window & { __tldw_pageAssist?: PageAssistDebug }
    w.__tldw_pageAssist = {
      setMessages: useStoreMessageOption.getState().setMessages,
      getMessages: () => useStoreMessageOption.getState().messages
    }

    return () => {
      delete w.__tldw_pageAssist
    }
  }, [])

  return (
    <PageAssistContext.Provider
      value={{
        controller,
        setController,

        embeddingController,
        setEmbeddingController
      }}>
      {children}
    </PageAssistContext.Provider>
  )
}
