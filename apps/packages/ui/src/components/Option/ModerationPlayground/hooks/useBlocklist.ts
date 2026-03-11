import React from "react"

import {
  appendManagedBlocklist,
  deleteManagedBlocklistItem,
  getBlocklist,
  getManagedBlocklist,
  lintBlocklist,
  updateBlocklist,
  type BlocklistLintResponse,
  type BlocklistManagedItem
} from "@/services/moderation"

export interface BlocklistState {
  rawText: string
  setRawText: React.Dispatch<React.SetStateAction<string>>
  rawLint: BlocklistLintResponse | null
  managedItems: BlocklistManagedItem[]
  managedVersion: string
  managedLine: string
  setManagedLine: React.Dispatch<React.SetStateAction<string>>
  managedLint: BlocklistLintResponse | null
  loading: boolean
  loadRaw: () => Promise<void>
  saveRaw: () => Promise<void>
  saveRawText: (text: string) => Promise<void>
  lintRaw: () => Promise<void>
  loadManaged: () => Promise<void>
  appendManaged: () => Promise<void>
  appendLine: (line: string) => Promise<void>
  deleteManaged: (itemId: number) => Promise<void>
  lintManagedLine: () => Promise<void>
  lintLine: (line: string) => Promise<BlocklistLintResponse>
}

export function useBlocklist(): BlocklistState {
  const [rawText, setRawText] = React.useState("")
  const [rawLint, setRawLint] = React.useState<BlocklistLintResponse | null>(null)
  const [managedItems, setManagedItems] = React.useState<BlocklistManagedItem[]>([])
  const [managedVersion, setManagedVersion] = React.useState("")
  const [managedLine, setManagedLine] = React.useState("")
  const [managedLint, setManagedLint] = React.useState<BlocklistLintResponse | null>(null)
  const [loading, setLoading] = React.useState(false)

  const loadRaw = React.useCallback(async () => {
    setLoading(true)
    try {
      const lines = await getBlocklist()
      setRawText((lines || []).join("\n"))
      setRawLint(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const saveRaw = React.useCallback(async () => {
    setLoading(true)
    try {
      const lines = rawText.split(/\r?\n/).map((line) => line.trimEnd())
      await updateBlocklist(lines)
    } finally {
      setLoading(false)
    }
  }, [rawText])

  const saveRawText = React.useCallback(async (text: string) => {
    setLoading(true)
    try {
      const lines = text.split(/\r?\n/).map((line) => line.trimEnd())
      await updateBlocklist(lines)
      setRawText(text)
      setRawLint(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const lintRaw = React.useCallback(async () => {
    setLoading(true)
    try {
      const lines = rawText.split(/\r?\n/)
      const lint = await lintBlocklist({ lines })
      setRawLint(lint)
    } finally {
      setLoading(false)
    }
  }, [rawText])

  const loadManaged = React.useCallback(async () => {
    setLoading(true)
    try {
      const { data, etag } = await getManagedBlocklist()
      setManagedItems(data.items || [])
      setManagedVersion(data.version || etag || "")
    } finally {
      setLoading(false)
    }
  }, [])

  const appendManaged = React.useCallback(async () => {
    if (!managedVersion) throw new Error("Load the managed blocklist first")
    const line = managedLine.trim()
    if (!line) throw new Error("Enter a line to append")
    setLoading(true)
    try {
      await appendManagedBlocklist(managedVersion, line)
      setManagedLine("")
      // Reload after append
      const { data, etag } = await getManagedBlocklist()
      setManagedItems(data.items || [])
      setManagedVersion(data.version || etag || "")
    } finally {
      setLoading(false)
    }
  }, [managedVersion, managedLine])

  const appendLine = React.useCallback(async (line: string) => {
    if (!managedVersion) throw new Error("Load the managed blocklist first")
    const trimmed = line.trim()
    if (!trimmed) throw new Error("Enter a line to append")
    setLoading(true)
    try {
      await appendManagedBlocklist(managedVersion, trimmed)
      setManagedLine("")
      const { data, etag } = await getManagedBlocklist()
      setManagedItems(data.items || [])
      setManagedVersion(data.version || etag || "")
    } finally {
      setLoading(false)
    }
  }, [managedVersion])

  const deleteManaged = React.useCallback(async (itemId: number) => {
    if (!managedVersion) return
    setLoading(true)
    try {
      await deleteManagedBlocklistItem(managedVersion, itemId)
      // Reload after delete
      const { data, etag } = await getManagedBlocklist()
      setManagedItems(data.items || [])
      setManagedVersion(data.version || etag || "")
    } finally {
      setLoading(false)
    }
  }, [managedVersion])

  const lintManagedLine = React.useCallback(async () => {
    if (!managedLine.trim()) throw new Error("Enter a line to lint")
    setLoading(true)
    try {
      const lint = await lintBlocklist({ line: managedLine.trim() })
      setManagedLint(lint)
    } finally {
      setLoading(false)
    }
  }, [managedLine])

  const lintLine = React.useCallback(async (line: string): Promise<BlocklistLintResponse> => {
    if (!line.trim()) throw new Error("Enter a line to lint")
    setLoading(true)
    try {
      const lint = await lintBlocklist({ line: line.trim() })
      setManagedLint(lint)
      return lint
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    rawText,
    setRawText,
    rawLint,
    managedItems,
    managedVersion,
    managedLine,
    setManagedLine,
    managedLint,
    loading,
    loadRaw,
    saveRaw,
    saveRawText,
    lintRaw,
    loadManaged,
    appendManaged,
    appendLine,
    deleteManaged,
    lintManagedLine,
    lintLine
  }
}
