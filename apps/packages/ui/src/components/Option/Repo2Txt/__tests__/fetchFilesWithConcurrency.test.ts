import { describe, expect, it } from "vitest"
import type { RepoFileContent, RepoTreeNode } from "../providers/types"
import { fetchFilesWithConcurrency } from "../fetchFilesWithConcurrency"

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

describe("fetchFilesWithConcurrency", () => {
  it("limits concurrent fetches", async () => {
    const nodes: RepoTreeNode[] = Array.from({ length: 7 }, (_, index) => ({
      path: `src/file-${index}.ts`,
      type: "blob",
      url: `src/file-${index}.ts`
    }))

    let inFlight = 0
    let maxInFlight = 0

    const provider = {
      fetchFile: async (node: RepoTreeNode): Promise<RepoFileContent> => {
        inFlight += 1
        maxInFlight = Math.max(maxInFlight, inFlight)
        await sleep(5)
        inFlight -= 1
        return {
          path: node.path,
          text: `content-${node.path}`,
          lineCount: 1
        }
      }
    }

    const progress: number[] = []
    const result = await fetchFilesWithConcurrency({
      nodes,
      provider,
      limit: 3,
      onProgress: (completed) => progress.push(completed)
    })

    expect(result).toHaveLength(nodes.length)
    expect(maxInFlight).toBeLessThanOrEqual(3)
    expect(progress.at(-1)).toBe(nodes.length)
  })
})
