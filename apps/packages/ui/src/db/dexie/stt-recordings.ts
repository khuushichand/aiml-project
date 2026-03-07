/**
 * Stub for STT recording persistence in Dexie (IndexedDB).
 * Replaced by Task 1 implementation.
 */

export async function saveSttRecording(_blob: Blob): Promise<string> {
  throw new Error("saveSttRecording stub - not yet implemented")
}

export async function getSttRecording(_id: string): Promise<Blob | null> {
  throw new Error("getSttRecording stub - not yet implemented")
}

export async function deleteSttRecording(_id: string): Promise<void> {
  throw new Error("deleteSttRecording stub - not yet implemented")
}
