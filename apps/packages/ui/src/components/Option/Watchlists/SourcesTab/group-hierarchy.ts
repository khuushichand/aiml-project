import type { WatchlistGroup } from "@/types/watchlists"

const toGroupId = (value: number | null | undefined): number | null =>
  typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null

export const collectDescendantGroupIds = (
  groups: WatchlistGroup[],
  groupId: number
): Set<number> => {
  const descendants = new Set<number>()
  const childrenByParent = new Map<number, number[]>()

  for (const group of groups) {
    const parentId = toGroupId(group.parent_group_id)
    if (!parentId) continue
    const existing = childrenByParent.get(parentId)
    if (existing) {
      existing.push(group.id)
    } else {
      childrenByParent.set(parentId, [group.id])
    }
  }

  const queue = [...(childrenByParent.get(groupId) || [])]
  while (queue.length > 0) {
    const nextId = queue.shift()
    if (!nextId || descendants.has(nextId)) continue
    descendants.add(nextId)
    const children = childrenByParent.get(nextId)
    if (children?.length) {
      queue.push(...children)
    }
  }

  return descendants
}

export const isGroupParentAssignmentCyclic = (
  groups: WatchlistGroup[],
  groupId: number,
  parentGroupId: number | null | undefined
): boolean => {
  const nextParentId = toGroupId(parentGroupId)
  if (!nextParentId) return false
  if (nextParentId === groupId) return true
  const descendants = collectDescendantGroupIds(groups, groupId)
  return descendants.has(nextParentId)
}

