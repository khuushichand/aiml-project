import { describe, expect, test, beforeEach } from "bun:test"
import { useDocumentWorkspaceStore } from "@tldw/ui/store/document-workspace"
import {
  DEFAULT_ZOOM_LEVEL,
  type OpenDocument,
  type DocumentType
} from "@tldw/ui/components/DocumentWorkspace/types"

describe("document workspace store - per-document state", () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useDocumentWorkspaceStore.getState().reset()
  })

  const createDoc = (id: number, type: DocumentType = "pdf"): OpenDocument => ({
    id,
    title: `Document ${id}`,
    type
  })

  test("openDocument initializes with default viewer state", () => {
    const store = useDocumentWorkspaceStore.getState()

    store.openDocument(createDoc(1))

    const state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(1)
    expect(state.currentPage).toBe(1)
    expect(state.totalPages).toBe(0)
    expect(state.zoomLevel).toBe(DEFAULT_ZOOM_LEVEL)
    expect(state.viewMode).toBe("single")
    expect(state.searchQuery).toBe("")
  })

  test("switching documents saves and restores viewer state", () => {
    const store = useDocumentWorkspaceStore.getState()

    // Open first document
    store.openDocument(createDoc(1))

    // Modify viewer state for doc 1
    useDocumentWorkspaceStore.getState().setCurrentPage(5)
    useDocumentWorkspaceStore.getState().setTotalPages(100)
    useDocumentWorkspaceStore.getState().setZoomLevel(150)
    useDocumentWorkspaceStore.getState().setViewMode("continuous")
    useDocumentWorkspaceStore.getState().setSearchQuery("test search")

    // Verify doc 1 state
    let state = useDocumentWorkspaceStore.getState()
    expect(state.currentPage).toBe(5)
    expect(state.zoomLevel).toBe(150)
    expect(state.viewMode).toBe("continuous")
    expect(state.searchQuery).toBe("test search")

    // Open second document (should save doc 1's state and initialize doc 2)
    useDocumentWorkspaceStore.getState().openDocument(createDoc(2))

    state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(2)
    expect(state.currentPage).toBe(1) // Reset for new doc
    expect(state.zoomLevel).toBe(DEFAULT_ZOOM_LEVEL) // Reset for new doc
    expect(state.viewMode).toBe("single") // Reset for new doc
    expect(state.searchQuery).toBe("") // Reset for new doc

    // Modify viewer state for doc 2
    useDocumentWorkspaceStore.getState().setCurrentPage(10)
    useDocumentWorkspaceStore.getState().setZoomLevel(200)

    // Switch back to doc 1 (should restore doc 1's state)
    useDocumentWorkspaceStore.getState().openDocument(createDoc(1))

    state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(1)
    expect(state.currentPage).toBe(5) // Restored
    expect(state.zoomLevel).toBe(150) // Restored
    expect(state.viewMode).toBe("continuous") // Restored
    expect(state.searchQuery).toBe("test search") // Restored

    // Switch back to doc 2 (should restore doc 2's state)
    useDocumentWorkspaceStore.getState().openDocument(createDoc(2))

    state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(2)
    expect(state.currentPage).toBe(10) // Restored
    expect(state.zoomLevel).toBe(200) // Restored
  })

  test("setActiveDocument saves and restores viewer state", () => {
    const store = useDocumentWorkspaceStore.getState()

    // Open two documents
    store.openDocument(createDoc(1))
    useDocumentWorkspaceStore.getState().setCurrentPage(7)
    useDocumentWorkspaceStore.getState().setZoomLevel(125)

    useDocumentWorkspaceStore.getState().openDocument(createDoc(2))
    useDocumentWorkspaceStore.getState().setCurrentPage(20)

    // Use setActiveDocument to switch back to doc 1
    useDocumentWorkspaceStore.getState().setActiveDocument(1)

    const state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(1)
    expect(state.currentPage).toBe(7) // Restored
    expect(state.zoomLevel).toBe(125) // Restored
  })

  test("closeDocument activates next document and restores its state", () => {
    const store = useDocumentWorkspaceStore.getState()

    // Open three documents
    store.openDocument(createDoc(1))
    useDocumentWorkspaceStore.getState().setCurrentPage(5)

    useDocumentWorkspaceStore.getState().openDocument(createDoc(2))
    useDocumentWorkspaceStore.getState().setCurrentPage(10)

    useDocumentWorkspaceStore.getState().openDocument(createDoc(3))
    useDocumentWorkspaceStore.getState().setCurrentPage(15)

    // Close active document (doc 3)
    useDocumentWorkspaceStore.getState().closeDocument(3)

    // Should activate first remaining document (doc 1) and restore its state
    const state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(1)
    expect(state.currentPage).toBe(5) // Restored from doc 1
  })

  test("closing non-active document preserves current state", () => {
    const store = useDocumentWorkspaceStore.getState()

    // Open two documents
    store.openDocument(createDoc(1))
    useDocumentWorkspaceStore.getState().openDocument(createDoc(2))
    useDocumentWorkspaceStore.getState().setCurrentPage(25)

    // Close non-active document (doc 1)
    useDocumentWorkspaceStore.getState().closeDocument(1)

    // Active document state should be unchanged
    const state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(2)
    expect(state.currentPage).toBe(25)
    expect(state.openDocuments).toHaveLength(1)
    expect(state.openDocuments[0].id).toBe(2)
  })

  test("closing all documents resets to defaults", () => {
    const store = useDocumentWorkspaceStore.getState()

    store.openDocument(createDoc(1))
    useDocumentWorkspaceStore.getState().setCurrentPage(50)
    useDocumentWorkspaceStore.getState().setZoomLevel(200)

    // Close the only document
    useDocumentWorkspaceStore.getState().closeDocument(1)

    const state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(null)
    expect(state.openDocuments).toHaveLength(0)
    expect(state.currentPage).toBe(1) // Default
    expect(state.zoomLevel).toBe(DEFAULT_ZOOM_LEVEL) // Default
    expect(state.viewMode).toBe("single") // Default
  })

  test("EPUB-specific state is preserved per document", () => {
    const store = useDocumentWorkspaceStore.getState()

    // Open EPUB document
    store.openDocument(createDoc(1, "epub"))
    useDocumentWorkspaceStore.getState().setCurrentCfi("epubcfi(/6/4!/2/2)")
    useDocumentWorkspaceStore.getState().setCurrentPercentage(35.5)
    useDocumentWorkspaceStore.getState().setCurrentChapterTitle("Chapter 3")

    // Open PDF document
    useDocumentWorkspaceStore.getState().openDocument(createDoc(2, "pdf"))
    useDocumentWorkspaceStore.getState().setCurrentPage(42)

    // Switch back to EPUB
    useDocumentWorkspaceStore.getState().openDocument(createDoc(1, "epub"))

    const state = useDocumentWorkspaceStore.getState()
    expect(state.currentCfi).toBe("epubcfi(/6/4!/2/2)")
    expect(state.currentPercentage).toBe(35.5)
    expect(state.currentChapterTitle).toBe("Chapter 3")
  })

  test("setActiveDocument to null resets viewer state", () => {
    const store = useDocumentWorkspaceStore.getState()

    store.openDocument(createDoc(1))
    useDocumentWorkspaceStore.getState().setCurrentPage(99)
    useDocumentWorkspaceStore.getState().setZoomLevel(300)

    // Deactivate document
    useDocumentWorkspaceStore.getState().setActiveDocument(null)

    const state = useDocumentWorkspaceStore.getState()
    expect(state.activeDocumentId).toBe(null)
    expect(state.currentPage).toBe(1)
    expect(state.zoomLevel).toBe(DEFAULT_ZOOM_LEVEL)
  })

  test("viewerState is stored in openDocuments array", () => {
    const store = useDocumentWorkspaceStore.getState()

    store.openDocument(createDoc(1))
    useDocumentWorkspaceStore.getState().setCurrentPage(88)
    useDocumentWorkspaceStore.getState().setZoomLevel(175)

    // Switch to another document to trigger state save
    useDocumentWorkspaceStore.getState().openDocument(createDoc(2))

    const state = useDocumentWorkspaceStore.getState()
    const doc1 = state.openDocuments.find((d) => d.id === 1)

    expect(doc1?.viewerState).toBeDefined()
    expect(doc1?.viewerState?.currentPage).toBe(88)
    expect(doc1?.viewerState?.zoomLevel).toBe(175)
  })
})
