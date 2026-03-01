import type { RepoTreeNode } from "../providers/types"

export type Repo2TxtFileTreeSlice = {
  nodes: RepoTreeNode[]
  selectedPaths: Set<string>
  setNodes: (nodes: RepoTreeNode[]) => void
}

export type Repo2TxtStoreState = Repo2TxtFileTreeSlice
