import React from "react"

import { testModeration, type ModerationTestResponse } from "@/services/moderation"

const MAX_HISTORY = 20

export interface TestHistoryEntry {
  phase: "input" | "output"
  text: string
  userId: string
  result: ModerationTestResponse
  timestamp: number
}

export interface ModerationTestState {
  phase: "input" | "output"
  setPhase: React.Dispatch<React.SetStateAction<"input" | "output">>
  text: string
  setText: React.Dispatch<React.SetStateAction<string>>
  userId: string
  setUserId: React.Dispatch<React.SetStateAction<string>>
  result: ModerationTestResponse | null
  history: TestHistoryEntry[]
  running: boolean
  runTest: () => Promise<void>
  runTestWith: (payload: { text: string; phase: "input" | "output"; userId?: string }) => Promise<void>
  clearHistory: () => void
  loadFromHistory: (entry: TestHistoryEntry) => void
}

export function useModerationTest(): ModerationTestState {
  const [phase, setPhase] = React.useState<"input" | "output">("input")
  const [text, setText] = React.useState("")
  const [userId, setUserId] = React.useState("")
  const [result, setResult] = React.useState<ModerationTestResponse | null>(null)
  const [history, setHistory] = React.useState<TestHistoryEntry[]>([])
  const [running, setRunning] = React.useState(false)

  const runTest = React.useCallback(async () => {
    if (!text.trim()) throw new Error("Enter sample text to test")
    setRunning(true)
    try {
      const payload = {
        user_id: userId ? userId.trim() : undefined,
        phase,
        text
      }
      const res = await testModeration(payload)
      setResult(res)
      const entry: TestHistoryEntry = {
        phase,
        text,
        userId,
        result: res,
        timestamp: Date.now()
      }
      setHistory((prev) => [entry, ...prev].slice(0, MAX_HISTORY))
    } finally {
      setRunning(false)
    }
  }, [text, userId, phase])

  const runTestWith = React.useCallback(async (payload: { text: string; phase: "input" | "output"; userId?: string }) => {
    if (!payload.text.trim()) throw new Error("Enter sample text to test")
    setRunning(true)
    try {
      const apiPayload = {
        user_id: payload.userId?.trim() || undefined,
        phase: payload.phase,
        text: payload.text
      }
      const res = await testModeration(apiPayload)
      setResult(res)
      setText(payload.text)
      setPhase(payload.phase)
      setUserId(payload.userId ?? "")
      const entry: TestHistoryEntry = {
        phase: payload.phase,
        text: payload.text,
        userId: payload.userId ?? "",
        result: res,
        timestamp: Date.now()
      }
      setHistory((prev) => [entry, ...prev].slice(0, MAX_HISTORY))
    } finally {
      setRunning(false)
    }
  }, [])

  const clearHistory = React.useCallback(() => {
    setHistory([])
  }, [])

  const loadFromHistory = React.useCallback((entry: TestHistoryEntry) => {
    setText(entry.text)
    setPhase(entry.phase)
    setUserId(entry.userId)
    setResult(entry.result)
  }, [])

  return {
    phase,
    setPhase,
    text,
    setText,
    userId,
    setUserId,
    result,
    history,
    running,
    runTest,
    runTestWith,
    clearHistory,
    loadFromHistory
  }
}
