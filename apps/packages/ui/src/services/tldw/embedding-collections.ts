import { bgRequestClient } from "@/services/background-proxy"

export type EmbeddingCollection = {
  name: string
  metadata?: Record<string, unknown>
}

const collectCollections = (
  source: unknown,
  output: EmbeddingCollection[]
) => {
  if (!source) return
  if (Array.isArray(source)) {
    for (const entry of source) {
      collectCollections(entry, output)
    }
    return
  }
  if (typeof source === "string" || typeof source === "number") {
    output.push({ name: String(source) })
    return
  }
  if (typeof source !== "object") return

  const record = source as Record<string, unknown>
  const name =
    record.name ??
    record.collection_name ??
    record.collection ??
    record.id ??
    record.value
  if (name) {
    output.push({
      name: String(name),
      metadata:
        record.metadata && typeof record.metadata === "object"
          ? (record.metadata as Record<string, unknown>)
          : undefined
    })
  }

  if ("collections" in record) {
    collectCollections(record.collections, output)
  }

  for (const [key, value] of Object.entries(record)) {
    if (key === "collections") continue
    collectCollections(value, output)
  }
}

const extractCollections = (source: unknown): EmbeddingCollection[] => {
  const output: EmbeddingCollection[] = []
  collectCollections(source, output)
  const seen = new Set<string>()
  return output.filter((entry) => {
    const key = entry.name.trim()
    if (!key) return false
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export const fetchEmbeddingCollections = async (): Promise<
  EmbeddingCollection[]
> => {
  try {
    const res = await bgRequestClient<any>({
      path: "/api/v1/embeddings/collections",
      method: "GET"
    })
    if (!res) return []
    return extractCollections(res)
  } catch {
    return []
  }
}
