import type { StateCreator } from "zustand"
import type { RepoTreeNode } from "../providers/types"
import type { Repo2TxtStoreState } from "./types"

const AUTO_SELECT_EXTENSIONS = new Set([
  "ts",
  "tsx",
  "js",
  "jsx",
  "py",
  "go",
  "rs",
  "java",
  "kt",
  "rb",
  "php",
  "cs",
  "cpp",
  "c",
  "h",
  "md",
  "json",
  "yml",
  "yaml"
])

const shouldAutoSelect = (node: RepoTreeNode): boolean => {
  if (node.type !== "blob") return false
  const match = node.path.toLowerCase().match(/\.([a-z0-9]+)$/)
  if (!match) return false
  return AUTO_SELECT_EXTENSIONS.has(match[1] ?? "")
}

export const createFileTreeSlice: StateCreator<
  Repo2TxtStoreState,
  [],
  [],
  Repo2TxtStoreState
> = (set) => ({
  nodes: [],
  selectedPaths: new Set<string>(),
  setNodes: (nodes) => {
    const selectedPaths = new Set<string>()
    for (const node of nodes) {
      if (shouldAutoSelect(node)) {
        selectedPaths.add(node.path)
      }
    }
    set({
      nodes,
      selectedPaths
    })
  },
  togglePath: (path) => {
    set((state) => {
      const nextSelected = new Set(state.selectedPaths)
      if (nextSelected.has(path)) {
        nextSelected.delete(path)
      } else {
        nextSelected.add(path)
      }
      return {
        selectedPaths: nextSelected
      }
    })
  }
})
