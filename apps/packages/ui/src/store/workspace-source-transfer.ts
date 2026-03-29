import type {
  WorkspaceSource,
  WorkspaceSourceFolder,
  WorkspaceSourceFolderMembership,
  WorkspaceSourceTransferInput,
  WorkspaceSourceTransferResult,
  WorkspaceSourceTransferSnapshot
} from "@/types/workspace"

const normalizeSourceFolderName = (name: string, fallbackName: string): string => {
  const trimmedName = name.trim()
  return trimmedName || fallbackName.trim()
}

const getUniqueSourceFolderName = (
  folders: WorkspaceSourceFolder[],
  name: string,
  parentFolderId: string | null,
  fallbackName: string,
  excludeFolderId?: string
): string => {
  const normalizedName = normalizeSourceFolderName(name, fallbackName)
  const siblingNames = new Set(
    folders
      .filter(
        (folder) =>
          folder.parentFolderId === parentFolderId &&
          folder.id !== excludeFolderId
      )
      .map((folder) => folder.name.trim().toLowerCase())
  )
  if (!siblingNames.has(normalizedName.toLowerCase())) {
    return normalizedName
  }

  let suffix = 2
  let candidate = `${normalizedName} (${suffix})`
  while (siblingNames.has(candidate.toLowerCase())) {
    suffix += 1
    candidate = `${normalizedName} (${suffix})`
  }
  return candidate
}

const cloneSource = (source: WorkspaceSource): WorkspaceSource => ({
  ...source,
  addedAt: source.addedAt instanceof Date ? source.addedAt : new Date(source.addedAt)
})

const cloneFolder = (folder: WorkspaceSourceFolder): WorkspaceSourceFolder => ({
  ...folder,
  createdAt:
    folder.createdAt instanceof Date ? folder.createdAt : new Date(folder.createdAt),
  updatedAt:
    folder.updatedAt instanceof Date ? folder.updatedAt : new Date(folder.updatedAt)
})

const cloneMembership = (
  membership: WorkspaceSourceFolderMembership
): WorkspaceSourceFolderMembership => ({ ...membership })

const cloneSnapshot = (
  snapshot: WorkspaceSourceTransferSnapshot
): WorkspaceSourceTransferSnapshot => ({
  workspaceId: snapshot.workspaceId,
  sources: snapshot.sources.map((source) => cloneSource(source)),
  sourceFolders: snapshot.sourceFolders.map((folder) => cloneFolder(folder)),
  sourceFolderMemberships: snapshot.sourceFolderMemberships.map((membership) =>
    cloneMembership(membership)
  )
})

const findMatchingSiblingFolder = (
  folders: WorkspaceSourceFolder[],
  parentFolderId: string | null,
  name: string,
  fallbackName: string,
  excludeFolderId?: string
): WorkspaceSourceFolder | null => {
  const normalizedName = normalizeSourceFolderName(name, fallbackName).toLowerCase()
  return (
    folders.find(
      (folder) =>
        folder.parentFolderId === parentFolderId &&
        folder.id !== excludeFolderId &&
        folder.name.trim().toLowerCase() === normalizedName
    ) || null
  )
}

const getFolderDepth = (
  foldersById: Map<string, WorkspaceSourceFolder>,
  folderId: string,
  cache: Map<string, number>
): number => {
  const cachedDepth = cache.get(folderId)
  if (cachedDepth !== undefined) {
    return cachedDepth
  }

  const folder = foldersById.get(folderId)
  if (!folder) {
    cache.set(folderId, 0)
    return 0
  }

  const parentFolderId = folder.parentFolderId
  if (!parentFolderId || parentFolderId === folderId) {
    cache.set(folderId, 0)
    return 0
  }

  const depth = getFolderDepth(foldersById, parentFolderId, cache) + 1
  cache.set(folderId, depth)
  return depth
}

const deleteOriginFolder = (
  snapshot: WorkspaceSourceTransferSnapshot,
  folderId: string,
  fallbackName: string
): void => {
  const folderToDelete = snapshot.sourceFolders.find((folder) => folder.id === folderId)
  if (!folderToDelete) {
    return
  }

  const remainingFolders = snapshot.sourceFolders.filter(
    (folder) => folder.id !== folderId
  )
  const reparentedFolders = new Map<string, WorkspaceSourceFolder>()
  const siblingPool = remainingFolders.filter(
    (folder) =>
      folder.parentFolderId !== folderId &&
      folder.parentFolderId === folderToDelete.parentFolderId
  )

  for (const folder of remainingFolders) {
    if (folder.parentFolderId !== folderId) {
      continue
    }

    const reparentedFolder = {
      ...folder,
      parentFolderId: folderToDelete.parentFolderId,
      name: getUniqueSourceFolderName(
        [...siblingPool, ...reparentedFolders.values()],
        folder.name,
        folderToDelete.parentFolderId,
        fallbackName,
        folder.id
      ),
      updatedAt: new Date()
    }
    reparentedFolders.set(folder.id, reparentedFolder)
  }

  const nextFolders = remainingFolders.map(
    (folder) => reparentedFolders.get(folder.id) || folder
  )

  snapshot.sourceFolders = nextFolders
  snapshot.sourceFolderMemberships = snapshot.sourceFolderMemberships.filter(
    (membership) => membership.folderId !== folderId
  )
}

export const applyWorkspaceSourceTransfer = (
  input: WorkspaceSourceTransferInput
): WorkspaceSourceTransferResult => {
  const originSnapshot = cloneSnapshot(input.originSnapshot)
  const destinationSnapshot = cloneSnapshot(input.destinationSnapshot)

  const originSourceById = new Map(
    originSnapshot.sources.map((source) => [source.id, source] as const)
  )
  const originFolderById = new Map(
    originSnapshot.sourceFolders.map((folder) => [folder.id, folder] as const)
  )
  const destinationSourceByMediaId = new Map<number, WorkspaceSource>()
  for (const source of destinationSnapshot.sources) {
    if (!destinationSourceByMediaId.has(source.mediaId)) {
      destinationSourceByMediaId.set(source.mediaId, source)
    }
  }

  const selectedSourceIdsByMediaId = new Map<number, string[]>()
  const selectedSourceByMediaId = new Map<number, WorkspaceSource>()
  const seenMediaIds = new Set<number>()

  for (const selectedSourceId of input.selectedSourceIds) {
    const source = originSourceById.get(selectedSourceId)
    if (!source) continue

    const mediaId = source.mediaId
    const selectedSourceIds = selectedSourceIdsByMediaId.get(mediaId) || []
    selectedSourceIdsByMediaId.set(mediaId, [...selectedSourceIds, source.id])

    if (!seenMediaIds.has(mediaId)) {
      seenMediaIds.add(mediaId)
      selectedSourceByMediaId.set(mediaId, source)
    }
  }

  const folderIdMap = new Map<string, string>()
  const transferredDestinationSourceIds: string[] = []
  const transferredMediaIds: number[] = []
  const conflictsResolved: number[] = []
  const conflictsSkipped: number[] = []
  const destinationMembershipKeySet = new Set(
    destinationSnapshot.sourceFolderMemberships.map(
      (membership) => `${membership.folderId}::${membership.sourceId}`
    )
  )

  const ensureDestinationFolder = (originFolderId: string | null): string | null => {
    if (!originFolderId) {
      return null
    }

    const existingMappedFolderId = folderIdMap.get(originFolderId)
    if (existingMappedFolderId) {
      return existingMappedFolderId
    }

    const originFolder = originFolderById.get(originFolderId)
    if (!originFolder) {
      return null
    }

    const mappedParentFolderId = ensureDestinationFolder(originFolder.parentFolderId)
    const matchingFolder = findMatchingSiblingFolder(
      destinationSnapshot.sourceFolders,
      mappedParentFolderId,
      originFolder.name,
      input.sourceFolderFallbackName
    )
    if (matchingFolder) {
      folderIdMap.set(originFolderId, matchingFolder.id)
      return matchingFolder.id
    }

    const nextFolder: WorkspaceSourceFolder = {
      ...cloneFolder(originFolder),
      id: input.generateId("folder"),
      workspaceId: destinationSnapshot.workspaceId,
      name: getUniqueSourceFolderName(
        destinationSnapshot.sourceFolders,
        originFolder.name,
        mappedParentFolderId,
        input.sourceFolderFallbackName
      ),
      parentFolderId: mappedParentFolderId
    }

    destinationSnapshot.sourceFolders.push(nextFolder)
    folderIdMap.set(originFolderId, nextFolder.id)
    return nextFolder.id
  }

  for (const mediaId of selectedSourceIdsByMediaId.keys()) {
    const source = selectedSourceByMediaId.get(mediaId)
    if (!source) {
      continue
    }

    const existingDestinationSource = destinationSourceByMediaId.get(mediaId)
    const conflictResolution = input.conflictResolutions[mediaId] || "skip"

    if (existingDestinationSource && conflictResolution === "skip") {
      conflictsSkipped.push(mediaId)
      continue
    }

    const destinationSource = existingDestinationSource
      ? existingDestinationSource
      : {
          ...cloneSource(source),
          id: input.generateId("source")
        }

    if (!existingDestinationSource) {
      destinationSnapshot.sources.push(destinationSource)
      destinationSourceByMediaId.set(mediaId, destinationSource)
    } else if (conflictResolution !== "skip") {
      conflictsResolved.push(mediaId)
    }

    const selectedSourceIdsForMediaId = selectedSourceIdsByMediaId.get(mediaId) || []
    const originMembershipFolderIds = originSnapshot.sourceFolderMemberships
      .filter((membership) => selectedSourceIdsForMediaId.includes(membership.sourceId))
      .map((membership) => membership.folderId)

    const transferredFolderIds: string[] = []
    const transferredFolderIdSet = new Set<string>()

    for (const originFolderId of originMembershipFolderIds) {
      const destinationFolderId = ensureDestinationFolder(originFolderId)
      if (!destinationFolderId || transferredFolderIdSet.has(destinationFolderId)) {
        continue
      }

      transferredFolderIdSet.add(destinationFolderId)
      transferredFolderIds.push(destinationFolderId)
    }

    if (
      existingDestinationSource &&
      conflictResolution === "replace-transferred-folders" &&
      transferredFolderIds.length > 0
    ) {
      destinationSnapshot.sourceFolderMemberships =
        destinationSnapshot.sourceFolderMemberships.filter(
          (membership) =>
            membership.sourceId !== destinationSource.id ||
            !transferredFolderIdSet.has(membership.folderId)
        )
      destinationMembershipKeySet.clear()
      for (const membership of destinationSnapshot.sourceFolderMemberships) {
        destinationMembershipKeySet.add(`${membership.folderId}::${membership.sourceId}`)
      }
    }

    for (const folderId of transferredFolderIds) {
      const membershipKey = `${folderId}::${destinationSource.id}`
      if (destinationMembershipKeySet.has(membershipKey)) {
        continue
      }

      destinationMembershipKeySet.add(membershipKey)
      destinationSnapshot.sourceFolderMemberships.push({
        folderId,
        sourceId: destinationSource.id
      })
    }

    transferredMediaIds.push(mediaId)
    transferredDestinationSourceIds.push(destinationSource.id)
  }

  const removedOriginSourceIds = new Set<string>()
  if (input.mode === "move") {
    for (const mediaId of transferredMediaIds) {
      for (const selectedSourceId of selectedSourceIdsByMediaId.get(mediaId) || []) {
        removedOriginSourceIds.add(selectedSourceId)
      }
    }

    originSnapshot.sources = originSnapshot.sources.filter(
      (source) => !removedOriginSourceIds.has(source.id)
    )
    originSnapshot.sourceFolderMemberships = originSnapshot.sourceFolderMemberships.filter(
      (membership) => !removedOriginSourceIds.has(membership.sourceId)
    )
  }

  const countMembershipsByFolderId = (
    memberships: WorkspaceSourceFolderMembership[]
  ): Map<string, number> => {
    const counts = new Map<string, number>()
    for (const membership of memberships) {
      counts.set(membership.folderId, (counts.get(membership.folderId) || 0) + 1)
    }
    return counts
  }

  const originMembershipCountsBefore = countMembershipsByFolderId(
    input.originSnapshot.sourceFolderMemberships
  )
  const originMembershipCountsAfter = countMembershipsByFolderId(
    originSnapshot.sourceFolderMemberships
  )
  const newlyEmptiedOriginFolderIds =
    input.mode === "move"
      ? originSnapshot.sourceFolders
          .filter((folder) => {
            const beforeCount = originMembershipCountsBefore.get(folder.id) || 0
            const afterCount = originMembershipCountsAfter.get(folder.id) || 0
            return beforeCount > 0 && afterCount === 0
          })
          .map((folder) => folder.id)
      : []

  if (input.mode === "move" && input.emptyFolderPolicy === "delete-empty-folders") {
    const foldersById = new Map(
      originSnapshot.sourceFolders.map((folder) => [folder.id, folder] as const)
    )
    const childrenByFolderId = new Map<string, string[]>(
      originSnapshot.sourceFolders.map((folder) => [folder.id, []])
    )
    for (const folder of originSnapshot.sourceFolders) {
      if (
        folder.parentFolderId &&
        folder.parentFolderId !== folder.id &&
        childrenByFolderId.has(folder.parentFolderId)
      ) {
        childrenByFolderId.get(folder.parentFolderId)?.push(folder.id)
      }
    }

    const candidateFolderIds = new Set<string>()
    for (const folderId of newlyEmptiedOriginFolderIds) {
      let currentFolderId: string | null = folderId
      while (currentFolderId) {
        if (candidateFolderIds.has(currentFolderId)) {
          break
        }
        candidateFolderIds.add(currentFolderId)
        const parentFolderId = foldersById.get(currentFolderId)?.parentFolderId || null
        currentFolderId =
          parentFolderId && parentFolderId !== currentFolderId
            ? parentFolderId
            : null
      }
    }

    const foldersToDelete = new Set<string>()
    let addedFolderId: string | null = null
    do {
      addedFolderId = null
      for (const folderId of candidateFolderIds) {
        if (foldersToDelete.has(folderId)) {
          continue
        }

        const folder = foldersById.get(folderId)
        if (!folder) {
          continue
        }

        const afterCount = originMembershipCountsAfter.get(folder.id) || 0
        if (afterCount > 0) {
          continue
        }

        const childFolderIds = childrenByFolderId.get(folder.id) || []
        if (
          childFolderIds.some((childFolderId) => !foldersToDelete.has(childFolderId))
        ) {
          continue
        }

        foldersToDelete.add(folder.id)
        addedFolderId = folder.id
      }
    } while (addedFolderId)

    const folderDepthCache = new Map<string, number>()
    const orderedFolderIdsToDelete = Array.from(foldersToDelete).sort(
      (leftFolderId, rightFolderId) =>
        getFolderDepth(foldersById, rightFolderId, folderDepthCache) -
        getFolderDepth(foldersById, leftFolderId, folderDepthCache)
    )

    for (const folderId of orderedFolderIdsToDelete) {
      deleteOriginFolder(originSnapshot, folderId, input.sourceFolderFallbackName)
    }
  }

  return {
    originSnapshot,
    destinationSnapshot,
    transferredMediaIds,
    transferredDestinationSourceIds,
    removedOriginSourceIds: Array.from(removedOriginSourceIds),
    newlyEmptiedOriginFolderIds,
    conflictsResolved,
    conflictsSkipped
  }
}
