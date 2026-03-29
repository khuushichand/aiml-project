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
