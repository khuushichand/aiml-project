import { create } from "zustand"
import type {
  DocumentWorkspaceStore,
  OpenDocument,
  DocumentViewerState,
  SidebarTab,
  RightPanelTab,
  ViewMode,
  Annotation,
  AnnotationSyncStatus,
  SearchResult,
  EpubTheme,
  EpubScrollMode,
  InsightDetailLevel
} from "@/components/DocumentWorkspace/types"
import {
  DEFAULT_ZOOM_LEVEL,
  MIN_ZOOM_LEVEL,
  MAX_ZOOM_LEVEL
} from "@/components/DocumentWorkspace/types"

const generateId = () =>
  `ann_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`

/**
 * Creates a default viewer state for a new document
 */
const createDefaultViewerState = (): DocumentViewerState => ({
  currentPage: 1,
  totalPages: 0,
  zoomLevel: DEFAULT_ZOOM_LEVEL,
  viewMode: "single",
  currentCfi: null,
  currentPercentage: 0,
  currentChapterTitle: null,
  searchQuery: "",
  searchResults: [],
  activeSearchIndex: 0
})

/**
 * Captures the current viewer state from the store
 */
const captureViewerState = (state: DocumentWorkspaceStore): DocumentViewerState => ({
  currentPage: state.currentPage,
  totalPages: state.totalPages,
  zoomLevel: state.zoomLevel,
  viewMode: state.viewMode,
  currentCfi: state.currentCfi,
  currentPercentage: state.currentPercentage,
  currentChapterTitle: state.currentChapterTitle,
  searchQuery: state.searchQuery,
  searchResults: state.searchResults,
  activeSearchIndex: state.activeSearchIndex
})

export const useDocumentWorkspaceStore = create<DocumentWorkspaceStore>(
  (set, get) => ({
    // Initial state
    activeDocumentId: null,
    activeDocumentType: null,
    openDocuments: [],
    leftSidebarCollapsed: false,
    rightPanelCollapsed: false,
    activeSidebarTab: "toc",
    activeRightTab: "chat",
    currentPage: 1,
    totalPages: 0,
    zoomLevel: DEFAULT_ZOOM_LEVEL,
    viewMode: "single",
    currentCfi: null,
    currentPercentage: 0,
    currentChapterTitle: null,
    epubTheme: "light",
    epubScrollMode: "paginated",
    insightDetailLevel: "standard",
    searchOpen: false,
    searchQuery: "",
    searchResults: [],
    activeSearchIndex: 0,
    annotations: [],
    pendingAnnotations: [],
    annotationSyncStatus: "synced",

    // Document management
    openDocument: (doc: OpenDocument) => {
      set((state) => {
        // Save current document's viewer state before switching
        let updatedOpenDocs = state.openDocuments
        if (state.activeDocumentId !== null && state.activeDocumentId !== doc.id) {
          updatedOpenDocs = state.openDocuments.map((d) =>
            d.id === state.activeDocumentId
              ? { ...d, viewerState: captureViewerState(state) }
              : d
          )
        }

        const existingDoc = updatedOpenDocs.find((d) => d.id === doc.id)
        if (existingDoc) {
          // Restore existing document's viewer state
          const viewerState = existingDoc.viewerState ?? createDefaultViewerState()
          return {
            openDocuments: updatedOpenDocs,
            activeDocumentId: doc.id,
            activeDocumentType: doc.type,
            currentPage: viewerState.currentPage,
            totalPages: viewerState.totalPages,
            zoomLevel: viewerState.zoomLevel,
            viewMode: viewerState.viewMode,
            currentCfi: viewerState.currentCfi,
            currentPercentage: viewerState.currentPercentage,
            currentChapterTitle: viewerState.currentChapterTitle,
            searchQuery: viewerState.searchQuery,
            searchResults: viewerState.searchResults,
            activeSearchIndex: viewerState.activeSearchIndex
          }
        }

        // Add new document with default viewer state
        const defaultState = createDefaultViewerState()
        return {
          openDocuments: [...updatedOpenDocs, { ...doc, viewerState: defaultState }],
          activeDocumentId: doc.id,
          activeDocumentType: doc.type,
          currentPage: defaultState.currentPage,
          totalPages: defaultState.totalPages,
          zoomLevel: defaultState.zoomLevel,
          viewMode: defaultState.viewMode,
          currentCfi: defaultState.currentCfi,
          currentPercentage: defaultState.currentPercentage,
          currentChapterTitle: defaultState.currentChapterTitle,
          searchQuery: defaultState.searchQuery,
          searchResults: defaultState.searchResults,
          activeSearchIndex: defaultState.activeSearchIndex
        }
      })
    },

    closeDocument: (id: number) => {
      set((state) => {
        const newOpenDocs = state.openDocuments.filter((d) => d.id !== id)
        const wasActive = state.activeDocumentId === id

        if (!wasActive) {
          return { openDocuments: newOpenDocs }
        }

        // If closing active document, activate the next available and restore its state
        const newActive = newOpenDocs.length > 0 ? newOpenDocs[0] : null
        if (!newActive) {
          const defaultState = createDefaultViewerState()
          return {
            openDocuments: newOpenDocs,
            activeDocumentId: null,
            activeDocumentType: null,
            currentPage: defaultState.currentPage,
            totalPages: defaultState.totalPages,
            zoomLevel: defaultState.zoomLevel,
            viewMode: defaultState.viewMode,
            currentCfi: defaultState.currentCfi,
            currentPercentage: defaultState.currentPercentage,
            currentChapterTitle: defaultState.currentChapterTitle,
            searchQuery: defaultState.searchQuery,
            searchResults: defaultState.searchResults,
            activeSearchIndex: defaultState.activeSearchIndex
          }
        }

        // Restore the new active document's viewer state
        const viewerState = newActive.viewerState ?? createDefaultViewerState()
        return {
          openDocuments: newOpenDocs,
          activeDocumentId: newActive.id,
          activeDocumentType: newActive.type,
          currentPage: viewerState.currentPage,
          totalPages: viewerState.totalPages,
          zoomLevel: viewerState.zoomLevel,
          viewMode: viewerState.viewMode,
          currentCfi: viewerState.currentCfi,
          currentPercentage: viewerState.currentPercentage,
          currentChapterTitle: viewerState.currentChapterTitle,
          searchQuery: viewerState.searchQuery,
          searchResults: viewerState.searchResults,
          activeSearchIndex: viewerState.activeSearchIndex
        }
      })
    },

    setActiveDocument: (id: number | null) => {
      set((state) => {
        // Save current document's viewer state before switching
        let updatedOpenDocs = state.openDocuments
        if (state.activeDocumentId !== null && state.activeDocumentId !== id) {
          updatedOpenDocs = state.openDocuments.map((d) =>
            d.id === state.activeDocumentId
              ? { ...d, viewerState: captureViewerState(state) }
              : d
          )
        }

        if (id === null) {
          const defaultState = createDefaultViewerState()
          return {
            openDocuments: updatedOpenDocs,
            activeDocumentId: null,
            activeDocumentType: null,
            currentPage: defaultState.currentPage,
            totalPages: defaultState.totalPages,
            zoomLevel: defaultState.zoomLevel,
            viewMode: defaultState.viewMode,
            currentCfi: defaultState.currentCfi,
            currentPercentage: defaultState.currentPercentage,
            currentChapterTitle: defaultState.currentChapterTitle,
            searchQuery: defaultState.searchQuery,
            searchResults: defaultState.searchResults,
            activeSearchIndex: defaultState.activeSearchIndex
          }
        }

        const doc = updatedOpenDocs.find((d) => d.id === id)
        if (!doc) return { openDocuments: updatedOpenDocs }

        // Restore the target document's viewer state
        const viewerState = doc.viewerState ?? createDefaultViewerState()
        return {
          openDocuments: updatedOpenDocs,
          activeDocumentId: id,
          activeDocumentType: doc.type,
          currentPage: viewerState.currentPage,
          totalPages: viewerState.totalPages,
          zoomLevel: viewerState.zoomLevel,
          viewMode: viewerState.viewMode,
          currentCfi: viewerState.currentCfi,
          currentPercentage: viewerState.currentPercentage,
          currentChapterTitle: viewerState.currentChapterTitle,
          searchQuery: viewerState.searchQuery,
          searchResults: viewerState.searchResults,
          activeSearchIndex: viewerState.activeSearchIndex
        }
      })
    },

    // Layout
    setLeftSidebarCollapsed: (collapsed: boolean) => {
      set({ leftSidebarCollapsed: collapsed })
    },

    setRightPanelCollapsed: (collapsed: boolean) => {
      set({ rightPanelCollapsed: collapsed })
    },

    setActiveSidebarTab: (tab: SidebarTab) => {
      set({ activeSidebarTab: tab })
    },

    setActiveRightTab: (tab: RightPanelTab) => {
      set({ activeRightTab: tab })
    },

    // Viewer
    setCurrentPage: (page: number) => {
      const { totalPages } = get()
      const clampedPage = Math.max(1, Math.min(page, totalPages || page))
      set({ currentPage: clampedPage })
    },

    setTotalPages: (total: number) => {
      set({ totalPages: total })
    },

    setZoomLevel: (zoom: number) => {
      const clampedZoom = Math.max(MIN_ZOOM_LEVEL, Math.min(zoom, MAX_ZOOM_LEVEL))
      set({ zoomLevel: clampedZoom })
    },

    setViewMode: (mode: ViewMode) => {
      set({ viewMode: mode })
    },

    goToNextPage: () => {
      const { currentPage, totalPages } = get()
      if (currentPage < totalPages) {
        set({ currentPage: currentPage + 1 })
      }
    },

    goToPreviousPage: () => {
      const { currentPage } = get()
      if (currentPage > 1) {
        set({ currentPage: currentPage - 1 })
      }
    },

    // EPUB-specific
    setCurrentCfi: (cfi: string | null) => {
      set({ currentCfi: cfi })
    },

    setCurrentPercentage: (percentage: number) => {
      set({ currentPercentage: percentage })
    },

    setCurrentChapterTitle: (title: string | null) => {
      set({ currentChapterTitle: title })
    },

    setEpubTheme: (theme: EpubTheme) => {
      set({ epubTheme: theme })
      // Persist to localStorage
      try {
        localStorage.setItem("epub-theme", theme)
      } catch (e) {
        // Ignore storage errors
      }
    },

    setEpubScrollMode: (mode: EpubScrollMode) => {
      set({ epubScrollMode: mode })
      // Persist to localStorage
      try {
        localStorage.setItem("epub-scroll-mode", mode)
      } catch (e) {
        // Ignore storage errors
      }
    },

    setInsightDetailLevel: (level: InsightDetailLevel) => {
      set({ insightDetailLevel: level })
      // Persist to localStorage
      try {
        localStorage.setItem("insight-detail-level", level)
      } catch (e) {
        // Ignore storage errors
      }
    },

    // Search
    setSearchOpen: (open: boolean) => {
      set({ searchOpen: open })
    },

    setSearchQuery: (query: string) => {
      set({ searchQuery: query })
    },

    setSearchResults: (results: SearchResult[]) => {
      set({ searchResults: results, activeSearchIndex: 0 })
    },

    setActiveSearchIndex: (index: number) => {
      const { searchResults } = get()
      if (index >= 0 && index < searchResults.length) {
        set({ activeSearchIndex: index })
      }
    },

    clearSearch: () => {
      set({
        searchQuery: "",
        searchResults: [],
        activeSearchIndex: 0
      })
    },

    // Annotations
    addAnnotation: (annotation) => {
      const now = new Date()
      const newAnnotation: Annotation = {
        ...annotation,
        id: generateId(),
        createdAt: now,
        updatedAt: now
      }
      set((state) => ({
        annotations: [...state.annotations, newAnnotation],
        pendingAnnotations: [...state.pendingAnnotations, newAnnotation],
        annotationSyncStatus: "pending"
      }))
    },

    updateAnnotation: (id: string, updates: Partial<Annotation>) => {
      set((state) => ({
        annotations: state.annotations.map((ann) =>
          ann.id === id ? { ...ann, ...updates, updatedAt: new Date() } : ann
        ),
        annotationSyncStatus: "pending"
      }))
    },

    removeAnnotation: (id: string) => {
      set((state) => ({
        annotations: state.annotations.filter((ann) => ann.id !== id),
        annotationSyncStatus: "pending"
      }))
    },

    setAnnotations: (annotations: Annotation[]) => {
      set({ annotations, pendingAnnotations: [], annotationSyncStatus: "synced" })
    },

    setAnnotationSyncStatus: (status: AnnotationSyncStatus) => {
      set({ annotationSyncStatus: status })
      if (status === "synced") {
        set({ pendingAnnotations: [] })
      }
    },

    // Reset
    reset: () => {
      set({
        activeDocumentId: null,
        activeDocumentType: null,
        openDocuments: [],
        leftSidebarCollapsed: false,
        rightPanelCollapsed: false,
        activeSidebarTab: "toc",
        activeRightTab: "chat",
        currentPage: 1,
        totalPages: 0,
        zoomLevel: DEFAULT_ZOOM_LEVEL,
        viewMode: "single",
        currentCfi: null,
        currentPercentage: 0,
        currentChapterTitle: null,
        epubTheme: "light",
        epubScrollMode: "paginated",
        insightDetailLevel: "standard",
        searchOpen: false,
        searchQuery: "",
        searchResults: [],
        activeSearchIndex: 0,
        annotations: [],
        pendingAnnotations: [],
        annotationSyncStatus: "synced"
      })
    }
  })
)

// Initialize settings from localStorage on module load
if (typeof window !== "undefined") {
  try {
    const savedTheme = localStorage.getItem("epub-theme")
    const savedScrollMode = localStorage.getItem("epub-scroll-mode")
    const savedDetailLevel = localStorage.getItem("insight-detail-level")
    if (savedTheme && ["light", "dark", "sepia"].includes(savedTheme)) {
      useDocumentWorkspaceStore.setState({ epubTheme: savedTheme as EpubTheme })
    }
    if (savedScrollMode && ["paginated", "continuous"].includes(savedScrollMode)) {
      useDocumentWorkspaceStore.setState({ epubScrollMode: savedScrollMode as EpubScrollMode })
    }
    if (savedDetailLevel && ["brief", "standard", "detailed"].includes(savedDetailLevel)) {
      useDocumentWorkspaceStore.setState({ insightDetailLevel: savedDetailLevel as InsightDetailLevel })
    }
  } catch (e) {
    // Ignore storage errors
  }
}
