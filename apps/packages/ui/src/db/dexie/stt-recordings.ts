import { db } from "./schema"
import type { SttRecordingRow } from "./types"

/** Maximum number of STT recordings kept in IndexedDB. */
export const STT_RECORDING_CAP = 20

/**
 * Persist an STT recording blob in IndexedDB.
 * Evicts the oldest recordings when the cap is exceeded.
 * @returns The generated recording id.
 */
export async function saveSttRecording(input: {
  blob: Blob
  durationMs: number
  mimeType: string
}): Promise<string> {
  const id = crypto.randomUUID()
  const row: SttRecordingRow = {
    id,
    blob: input.blob,
    mimeType: input.mimeType,
    durationMs: input.durationMs,
    createdAt: Date.now()
  }

  // Evict oldest entries when at or over the cap
  const count = await db.sttRecordings.count()
  if (count >= STT_RECORDING_CAP) {
    const overflow = count - STT_RECORDING_CAP + 1
    const oldest = await db.sttRecordings
      .orderBy("createdAt")
      .toArray()
    const idsToDelete = oldest.slice(0, overflow).map((r) => r.id)
    if (idsToDelete.length > 0) {
      await db.sttRecordings.bulkDelete(idsToDelete)
    }
  }

  await db.sttRecordings.put(row)
  return id
}

/**
 * Retrieve a single STT recording by id.
 */
export async function getSttRecording(
  id: string
): Promise<SttRecordingRow | undefined> {
  return await db.sttRecordings.get(id)
}

/**
 * Delete a single STT recording by id.
 */
export async function deleteSttRecording(id: string): Promise<void> {
  await db.sttRecordings.delete(id)
}

/**
 * List all STT recordings, sorted by createdAt descending (most recent first).
 */
export async function listSttRecordings(): Promise<SttRecordingRow[]> {
  return await db.sttRecordings
    .orderBy("createdAt")
    .reverse()
    .toArray()
}
