import { useCallback, useMemo, useReducer } from "react"

import { getChatLoopEvents, startChatLoop } from "@/services/chat-loop/client"
import { createInitialChatLoopState, reduceLoopEvent } from "@/services/chat-loop/reducer"
import type { ChatLoopEvent } from "@/services/chat-loop/types"

type ChatLoopAction =
  | { type: "event"; event: ChatLoopEvent }
  | { type: "reset" }

export function useChatLoopState() {
  const [state, dispatchBase] = useReducer(
    (prev: ReturnType<typeof createInitialChatLoopState>, action: ChatLoopAction) => {
      if (action.type === "reset") {
        return createInitialChatLoopState()
      }
      return reduceLoopEvent(prev, action.event)
    },
    undefined,
    createInitialChatLoopState,
  )

  const dispatch = useCallback((event: ChatLoopEvent) => {
    dispatchBase({ type: "event", event })
  }, [])

  const reset = useCallback(() => {
    dispatchBase({ type: "reset" })
  }, [])

  const applyEvents = useCallback((events: ChatLoopEvent[]) => {
    for (const event of events) {
      dispatch(event)
    }
  }, [])

  const startRun = useCallback(
    async (messages: Array<Record<string, unknown>>) => {
      const started = await startChatLoop({ messages })
      dispatch({
        run_id: started.run_id,
        seq: 1,
        event: "run_started",
        data: {},
      })
      return started.run_id
    },
    [],
  )

  const pollEvents = useCallback(
    async (runId: string) => {
      const response = await getChatLoopEvents(runId, state.lastSeq)
      applyEvents(response.events)
      return response.events
    },
    [applyEvents, state.lastSeq],
  )

  return useMemo(
    () => ({
      state,
      dispatch,
      reset,
      applyEvents,
      startRun,
      pollEvents,
    }),
    [state, dispatch, reset, applyEvents, startRun, pollEvents],
  )
}
