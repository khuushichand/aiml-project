import React from "react"

export const useDeferredComposerInput = (value: string) => {
  const liveInput = value
  const deferredInput = React.useDeferredValue(value)
  return {
    liveInput,
    deferredInput
  }
}

