import React from "react"

type LayoutEffectsOwnerState = {
  ownerId?: string
}

const getLayoutEffectsOwnerState = (): LayoutEffectsOwnerState | null => {
  if (typeof globalThis === "undefined") return null
  const scope = globalThis as typeof globalThis & {
    __tldwLayoutEffectsOwner?: LayoutEffectsOwnerState
  }
  if (!scope.__tldwLayoutEffectsOwner) {
    scope.__tldwLayoutEffectsOwner = {}
  }
  return scope.__tldwLayoutEffectsOwner
}

type LayoutEffectsOwnerOptions = {
  prefer?: boolean
}

export const useLayoutEffectsOwner = (
  options: LayoutEffectsOwnerOptions = {}
) => {
  const { prefer = false } = options
  const ownerId = React.useId()
  const [isOwner, setIsOwner] = React.useState(false)
  const useEffectHook = prefer ? React.useLayoutEffect : React.useEffect

  useEffectHook(() => {
    const state = getLayoutEffectsOwnerState()
    if (!state) {
      setIsOwner(true)
      return
    }

    if (!state.ownerId) {
      state.ownerId = ownerId
      setIsOwner(true)
    } else {
      setIsOwner(state.ownerId === ownerId)
    }

    return () => {
      if (state.ownerId === ownerId) {
        state.ownerId = undefined
      }
    }
  }, [ownerId])

  return isOwner
}
