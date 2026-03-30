import React from "react"

export function useWorldBookTestMatching() {
  const [openTestMatching, setOpenTestMatching] = React.useState(false)
  const [testMatchingWorldBookId, setTestMatchingWorldBookId] = React.useState<number | null>(null)

  const openTestMatchingModal = React.useCallback((worldBookId?: number | null) => {
    if (typeof worldBookId === "number" && Number.isFinite(worldBookId) && worldBookId > 0) {
      setTestMatchingWorldBookId(worldBookId)
    } else {
      setTestMatchingWorldBookId(null)
    }
    setOpenTestMatching(true)
  }, [])

  const closeTestMatchingModal = React.useCallback(() => {
    setOpenTestMatching(false)
  }, [])

  return {
    openTestMatching,
    testMatchingWorldBookId,
    openTestMatchingModal,
    closeTestMatchingModal,
  }
}
