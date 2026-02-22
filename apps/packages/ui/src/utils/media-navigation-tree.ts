import type { MediaNavigationNode } from "@/hooks/useMediaNavigation"

export type MediaNavigationTreeIndex = {
  byId: Record<string, MediaNavigationNode>
  childrenByParent: Record<string, MediaNavigationNode[]>
  roots: MediaNavigationNode[]
}

export const compareMediaNavigationNodes = (
  a: MediaNavigationNode,
  b: MediaNavigationNode
) => {
  if (a.order !== b.order) return a.order - b.order
  if (a.level !== b.level) return a.level - b.level
  const aPath = a.path_label || ""
  const bPath = b.path_label || ""
  if (aPath !== bPath) return aPath.localeCompare(bPath)
  return a.title.localeCompare(b.title)
}

export const sortMediaNavigationNodes = (
  nodes: MediaNavigationNode[]
): MediaNavigationNode[] => [...nodes].sort(compareMediaNavigationNodes)

export const buildMediaNavigationTreeIndex = (
  nodes: MediaNavigationNode[]
): MediaNavigationTreeIndex => {
  const byId: Record<string, MediaNavigationNode> = {}
  for (const node of nodes) byId[node.id] = node

  const childrenByParent: Record<string, MediaNavigationNode[]> = {}
  const roots: MediaNavigationNode[] = []

  for (const node of nodes) {
    const parentId =
      node.parent_id && byId[node.parent_id] ? node.parent_id : "__root__"
    if (parentId === "__root__") {
      roots.push(node)
      continue
    }
    if (!childrenByParent[parentId]) childrenByParent[parentId] = []
    childrenByParent[parentId].push(node)
  }

  roots.sort(compareMediaNavigationNodes)
  for (const key of Object.keys(childrenByParent)) {
    childrenByParent[key].sort(compareMediaNavigationNodes)
  }

  return { byId, childrenByParent, roots }
}

const normalize = (value: string) => value.trim().toLowerCase()

export const findQuickJumpMatches = (
  nodes: MediaNavigationNode[],
  query: string,
  limit = 8
): MediaNavigationNode[] => {
  const q = normalize(query)
  if (!q) return []

  const exactPath = nodes.filter((n) => normalize(n.path_label || "") === q)
  if (exactPath.length > 0) {
    return exactPath.sort(compareMediaNavigationNodes).slice(0, limit)
  }

  const prefixPath = nodes.filter((n) =>
    normalize(n.path_label || "").startsWith(q)
  )
  if (prefixPath.length > 0) {
    return prefixPath.sort(compareMediaNavigationNodes).slice(0, limit)
  }

  const titleContains = nodes.filter((n) => normalize(n.title).includes(q))
  return titleContains.sort(compareMediaNavigationNodes).slice(0, limit)
}
