import { describe, expect, it } from "vitest"
import {
  characterImportQueueReducer,
  initialCharacterImportQueueState,
  shouldHandleImportUploadEvent,
  summarizeCharacterImportQueue,
  toCharacterImportPreviewMode
} from "../import-state-model"

describe("character import state model", () => {
  it("queues files in queued state", () => {
    const state = characterImportQueueReducer(initialCharacterImportQueueState, {
      type: "queue/replace",
      files: [
        { id: "f1", fileName: "one.json" },
        { id: "f2", fileName: "two.json" }
      ]
    })

    expect(state.items).toEqual([
      { id: "f1", fileName: "one.json", state: "queued", message: null },
      { id: "f2", fileName: "two.json", state: "queued", message: null }
    ])
  })

  it("transitions file lifecycle through processing, success, and failure", () => {
    const queued = characterImportQueueReducer(initialCharacterImportQueueState, {
      type: "queue/replace",
      files: [
        { id: "f1", fileName: "one.json" },
        { id: "f2", fileName: "two.json" }
      ]
    })
    const processing = characterImportQueueReducer(queued, {
      type: "item/processing",
      id: "f1"
    })
    const success = characterImportQueueReducer(processing, {
      type: "item/success",
      id: "f1",
      message: "Imported"
    })
    const failed = characterImportQueueReducer(success, {
      type: "item/failure",
      id: "f2",
      message: "Invalid payload"
    })

    expect(failed.items).toEqual([
      { id: "f1", fileName: "one.json", state: "success", message: "Imported" },
      {
        id: "f2",
        fileName: "two.json",
        state: "failure",
        message: "Invalid payload"
      }
    ])
  })

  it("tracks drag enter/leave state", () => {
    const entered = characterImportQueueReducer(initialCharacterImportQueueState, {
      type: "drag/enter"
    })
    const left = characterImportQueueReducer(entered, { type: "drag/leave" })

    expect(entered.dragState).toBe("drag-over")
    expect(left.dragState).toBe("idle")
  })

  it("summarizes queue counts compatible with batch summary messaging", () => {
    const summary = summarizeCharacterImportQueue([
      { id: "1", fileName: "a.json", state: "success", message: null },
      { id: "2", fileName: "b.json", state: "failure", message: "bad yaml" },
      { id: "3", fileName: "c.json", state: "queued", message: null },
      { id: "4", fileName: "d.json", state: "processing", message: null }
    ])

    expect(summary).toEqual({
      total: 4,
      queued: 1,
      processing: 1,
      success: 1,
      failure: 1,
      complete: false
    })
  })

  it("handles single-file and multi-file upload callback gating", () => {
    const single = shouldHandleImportUploadEvent({
      file: {
        uid: "one",
        name: "single.json",
        size: 10,
        lastModified: 1
      },
      fileList: []
    })
    const multiFirstByUid = shouldHandleImportUploadEvent({
      file: {
        uid: "first",
        name: "a.json",
        size: 10,
        lastModified: 1
      },
      fileList: [
        { uid: "first", name: "a.json", size: 10, lastModified: 1 },
        { uid: "second", name: "b.json", size: 20, lastModified: 2 }
      ]
    })
    const multiLaterByUid = shouldHandleImportUploadEvent({
      file: {
        uid: "second",
        name: "b.json",
        size: 20,
        lastModified: 2
      },
      fileList: [
        { uid: "first", name: "a.json", size: 10, lastModified: 1 },
        { uid: "second", name: "b.json", size: 20, lastModified: 2 }
      ]
    })
    const multiFirstByMetadata = shouldHandleImportUploadEvent({
      file: {
        name: "same.json",
        size: 50,
        lastModified: 5
      },
      fileList: [
        { name: "same.json", size: 50, lastModified: 5 },
        { name: "other.json", size: 55, lastModified: 6 }
      ]
    })

    expect(single).toBe(true)
    expect(multiFirstByUid).toBe(true)
    expect(multiLaterByUid).toBe(false)
    expect(multiFirstByMetadata).toBe(true)
  })

  it("labels preview mode as single or batch", () => {
    expect(toCharacterImportPreviewMode(1)).toBe("single")
    expect(toCharacterImportPreviewMode(2)).toBe("batch")
  })
})
