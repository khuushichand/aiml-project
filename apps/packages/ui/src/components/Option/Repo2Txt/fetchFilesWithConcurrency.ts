import type {
  IProvider,
  RepoFileContent,
  RepoTreeNode
} from "./providers/types"

type FetchFilesWithConcurrencyOptions = {
  nodes: RepoTreeNode[]
  provider: Pick<IProvider, "fetchFile">
  limit?: number
  onProgress?: (completed: number, total: number) => void
}

export async function fetchFilesWithConcurrency({
  nodes,
  provider,
  limit = 5,
  onProgress
}: FetchFilesWithConcurrencyOptions): Promise<RepoFileContent[]> {
  if (nodes.length === 0) {
    onProgress?.(0, 0)
    return []
  }

  const safeLimit = Math.max(1, Math.floor(limit))
  const result: RepoFileContent[] = new Array(nodes.length)
  let cursor = 0
  let completed = 0

  const worker = async () => {
    while (true) {
      const index = cursor
      cursor += 1
      if (index >= nodes.length) {
        return
      }
      const content = await provider.fetchFile(nodes[index])
      result[index] = content
      completed += 1
      onProgress?.(completed, nodes.length)
    }
  }

  const workers = Array.from(
    { length: Math.min(safeLimit, nodes.length) },
    () => worker()
  )
  await Promise.all(workers)
  return result
}
