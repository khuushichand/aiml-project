/**
 * GraphCanvas Component
 *
 * Cytoscape.js graph renderer for the timeline view.
 * Handles graph rendering, layout, and user interactions.
 */

import React, { useRef, useEffect, useCallback } from 'react'
import cytoscape, { Core, NodeSingular, EdgeSingular } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { useTimelineStore } from '@/store/timeline'

// Register dagre layout
cytoscape.use(dagre)

// ============================================================================
// Styles
// ============================================================================

type DagreLayoutOptions = cytoscape.LayoutOptions & {
  rankDir?: string
  nodeSep?: number
  rankSep?: number
  animationDuration?: number
}

const buildLayoutOptions = (
  direction: ReturnType<typeof useTimelineStore.getState>['settings']['layoutDirection'],
  nodeSeparation: number,
  rankSeparation: number
): DagreLayoutOptions => ({
  name: 'dagre',
  rankDir: direction,
  nodeSep: nodeSeparation,
  rankSep: rankSeparation,
  animate: true,
  animationDuration: 300
})

const getCytoscapeStyles = (
  settings: ReturnType<typeof useTimelineStore.getState>['settings']
): cytoscape.StylesheetJson => [
  // Cytoscape's typed stylesheet helpers are fairly limited, so we define
  // styles with plain objects and cast to `any` at the leaf level. If this
  // becomes hard to maintain, consider introducing a small wrapper with
  // stricter types around `style` definitions.
  // Base node style
  {
    selector: 'node',
    style: {
      'background-color': '#666',
      'label': 'data(label)',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '10px',
      'color': '#fff',
      'text-wrap': 'ellipsis',
      'text-max-width': `${settings.nodeWidth - 20}px`,
      'width': settings.nodeWidth,
      'height': settings.nodeHeight,
      'shape': settings.nodeShape,
      'border-width': 2,
      'border-color': 'transparent',
      'text-outline-width': 1,
      'text-outline-color': '#000'
    }
  },

  // Root node
  {
    selector: 'node[type="root"]',
    style: {
      'background-color': '#374151',
      'label': 'Start',
      'shape': 'diamond',
      'width': 60,
      'height': 60
    }
  },

  // User message nodes
  {
    selector: 'node[role="user"]',
    style: {
      'background-color': settings.userNodeColor
    }
  },

  // Assistant message nodes
  {
    selector: 'node[role="assistant"]',
    style: {
      'background-color': settings.assistantNodeColor,
      'color': '#000',
      'text-outline-color': '#fff',
      'border-color': '#ccc',
      'border-width': 1
    }
  },

  // System message nodes
  {
    selector: 'node[role="system"]',
    style: {
      'background-color': settings.systemNodeColor
    }
  },

  // Swipe nodes (alternative responses)
  {
    selector: 'node[is_swipe="true"]',
    style: {
      'border-width': 3,
      'border-style': 'dashed',
      'border-color': '#f59e0b',
      'opacity': 0.85
    }
  },

  // Nodes with swipes indicator
  {
    selector: 'node[has_swipes="true"]',
    style: {
      'border-width': 3,
      'border-color': '#f59e0b'
    }
  },

  // Selected node
  {
    selector: 'node:selected',
    style: {
      'border-width': 4,
      'border-color': '#22c55e',
      'background-blacken': -0.1
    }
  },

  // Highlighted nodes (from search)
  {
    selector: 'node.highlighted',
    style: {
      'border-width': 4,
      'border-color': '#fbbf24',
      'background-blacken': -0.2
    }
  },

  // Hovered node
  {
    selector: 'node:active',
    style: {
      'overlay-opacity': 0.2,
      'overlay-color': '#fff'
    }
  },

  // Current conversation nodes
  {
    selector: 'node[is_current="true"]',
    style: {
      'background-blacken': -0.1
    }
  },

  // Base edge style
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': settings.edgeColor,
      'target-arrow-color': settings.edgeColor,
      'target-arrow-shape': 'triangle',
      'curve-style': settings.curveStyle,
      'arrow-scale': 0.8
    }
  },

  // Swipe edges
  {
    selector: 'edge[is_swipe_edge="true"]',
    style: {
      'line-style': 'dashed',
      'line-color': '#f59e0b',
      'target-arrow-color': '#f59e0b',
      'opacity': 0.7
    }
  },

  // Selected edge
  {
    selector: 'edge:selected',
    style: {
      'width': 3,
      'line-color': '#22c55e',
      'target-arrow-color': '#22c55e'
    }
  },

  // Highlighted edges
  {
    selector: 'edge.highlighted',
    style: {
      'width': 3,
      'line-color': '#fbbf24',
      'target-arrow-color': '#fbbf24'
    }
  }
]

// ============================================================================
// Component
// ============================================================================

export const GraphCanvas: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const longPressTimerRef = useRef<NodeJS.Timeout | null>(null)

  const {
    graph,
    settings,
    selectedNodeId,
    highlightedNodeIds,
    selectNode,
    hoverNode,
    toggleSwipeExpansion,
    getVisibleNodes,
    updateSettings
  } = useTimelineStore()

  const settingsRef = useRef(settings)
  const selectNodeRef = useRef(selectNode)
  const hoverNodeRef = useRef(hoverNode)
  const toggleSwipeExpansionRef = useRef(toggleSwipeExpansion)
  const updateSettingsRef = useRef(updateSettings)
  const buildElementsRef = useRef<() => cytoscape.ElementDefinition[]>(() => [])

  useEffect(() => {
    settingsRef.current = settings
  }, [settings])

  useEffect(() => {
    selectNodeRef.current = selectNode
  }, [selectNode])

  useEffect(() => {
    hoverNodeRef.current = hoverNode
  }, [hoverNode])

  useEffect(() => {
    toggleSwipeExpansionRef.current = toggleSwipeExpansion
  }, [toggleSwipeExpansion])

  useEffect(() => {
    updateSettingsRef.current = updateSettings
  }, [updateSettings])

  // Convert graph data to Cytoscape elements
  const buildElements = useCallback(() => {
    if (!graph) return []

    const visibleNodes = getVisibleNodes()
    const visibleNodeIds = new Set(visibleNodes.map((n) => n.id))

    // Build node elements
    const nodeElements = visibleNodes.map((node) => ({
      data: {
        id: node.id,
        label: truncateText(node.content, 50),
        type: node.type,
        role: node.role,
        is_current: String(node.is_current),
        is_swipe: String(node.is_swipe),
        has_swipes: String(node.has_swipes),
        swipe_count: node.swipe_count,
        timestamp: node.timestamp,
        message_ids: node.message_ids.join(','),
        history_ids: node.history_ids.join(',')
      }
    }))

    // Build edge elements (only for visible nodes)
    const edgeElements = graph.edges
      .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
      .map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          is_swipe_edge: String(edge.is_swipe_edge),
          history_ids: edge.history_ids.join(',')
        }
      }))

    return [...nodeElements, ...edgeElements]
  }, [graph, getVisibleNodes])

  useEffect(() => {
    buildElementsRef.current = buildElements
  }, [buildElements])

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current) return

    const initialSettings = settingsRef.current
    const cy = cytoscape({
      container: containerRef.current,
      elements: buildElementsRef.current(),
      style: getCytoscapeStyles(initialSettings),
      layout: buildLayoutOptions(
        initialSettings.layoutDirection,
        initialSettings.nodeSeparation,
        initialSettings.rankSeparation
      ),
      wheelSensitivity: 0.2,
      minZoom: initialSettings.minZoom,
      maxZoom: initialSettings.maxZoom,
      boxSelectionEnabled: false,
      autounselectify: false
    })

    cyRef.current = cy

    // ========================================================================
    // Event Handlers
    // ========================================================================

    // Node click - select
    cy.on('tap', 'node', (evt) => {
      const node = evt.target as NodeSingular
      selectNodeRef.current(node.id())
    })

    // Node double-click - could navigate to message
    cy.on('dbltap', 'node', (evt) => {
      const node = evt.target as NodeSingular
      // TODO: Implement navigation to message
      console.log('Double-clicked node:', node.id())
    })

    // Long press on node - toggle swipe expansion
    cy.on('tapstart', 'node', (evt) => {
      const node = evt.target as NodeSingular
      const nodeData = node.data()

      if (nodeData.has_swipes === 'true') {
        longPressTimerRef.current = setTimeout(() => {
          toggleSwipeExpansionRef.current(node.id())
          longPressTimerRef.current = null
        }, 500) // 500ms long press
      }
    })

    cy.on('tapend', () => {
      if (longPressTimerRef.current) {
        clearTimeout(longPressTimerRef.current)
        longPressTimerRef.current = null
      }
    })

    // Node hover
    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target as NodeSingular
      hoverNodeRef.current(node.id())
      containerRef.current!.style.cursor = 'pointer'
    })

    cy.on('mouseout', 'node', () => {
      hoverNodeRef.current(null)
      containerRef.current!.style.cursor = 'default'
    })

    // Edge click
    cy.on('tap', 'edge', (evt) => {
      const edge = evt.target as EdgeSingular
      // Select the target node of the edge
      selectNodeRef.current(edge.target().id())
    })

    // Background click - deselect
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        selectNodeRef.current(null)
      }
    })

    // Sync zoom level back to store (so toolbar controls are relative to current zoom)
    cy.on('zoom', () => {
      const currentZoom = cy.zoom()
      const storeZoom = useTimelineStore.getState().settings.zoomLevel
      if (Math.abs(storeZoom - currentZoom) < 0.001) return
      updateSettingsRef.current({ zoomLevel: currentZoom })
    })

    // Cleanup
    return () => {
      if (longPressTimerRef.current) {
        clearTimeout(longPressTimerRef.current)
      }
      cy.destroy()
      cyRef.current = null
    }
  }, []) // Only run once on mount

  // Update elements when graph changes
  useEffect(() => {
    if (!cyRef.current || !graph) return

    const cy = cyRef.current
    const elements = buildElements()

    // Simple full rebuild: remove all elements and re-add them on graph changes.
    // This keeps the implementation straightforward; if timeline graphs grow
    // large enough to cause visible flicker, we can switch to Cytoscape's
    // incremental diff/patch APIs to update only changed nodes/edges.
    cy.elements().remove()
    cy.add(elements)

    // Re-run layout
    cy
      .layout(
        buildLayoutOptions(
          settings.layoutDirection,
          settings.nodeSeparation,
          settings.rankSeparation
        )
      )
      .run()

    // Fit to viewport
    cy.fit(undefined, 50)
  }, [
    graph,
    buildElements,
    settings.layoutDirection,
    settings.nodeSeparation,
    settings.rankSeparation
  ])

  // Update styles when settings change
  useEffect(() => {
    if (!cyRef.current) return
    cyRef.current.style(getCytoscapeStyles(settings))
  }, [settings])

  // Apply zoom level changes from toolbar/settings
  useEffect(() => {
    if (!cyRef.current) return

    const cy = cyRef.current
    const clampedZoom = Math.min(settings.maxZoom, Math.max(settings.minZoom, settings.zoomLevel))

    if (Math.abs(cy.zoom() - clampedZoom) < 0.001) return
    cy.zoom(clampedZoom)
  }, [settings.zoomLevel, settings.minZoom, settings.maxZoom])

  // Update selection state
  useEffect(() => {
    if (!cyRef.current) return
    const cy = cyRef.current

    // Clear previous selection
    cy.nodes().unselect()

    // Select current node
    if (selectedNodeId) {
      cy.getElementById(selectedNodeId).select()
    }
  }, [selectedNodeId])

  // Update highlighted nodes
  useEffect(() => {
    if (!cyRef.current) return
    const cy = cyRef.current

    // Clear previous highlights
    cy.elements().removeClass('highlighted')

    // Apply new highlights
    highlightedNodeIds.forEach((nodeId) => {
      const node = cy.getElementById(nodeId)
      if (node) {
        node.addClass('highlighted')
        // Also highlight edges to/from this node
        node.connectedEdges().addClass('highlighted')
      }
    })

    // If there are highlighted nodes, zoom to fit them
    if (highlightedNodeIds.size > 0) {
      const highlightedNodes = cy.nodes('.highlighted')
      if (highlightedNodes.length > 0) {
        cy.animate({
          fit: {
            eles: highlightedNodes,
            padding: 50
          },
          duration: 300
        })
      }
    }
  }, [highlightedNodeIds])

  return (
    <div
      ref={containerRef}
      className="graph-canvas"
      style={{
        width: '100%',
        height: '100%',
        background: 'var(--bg-secondary, #111)'
      }}
    />
  )
}

// ============================================================================
// Helpers
// ============================================================================

function truncateText(text: string, maxLength: number): string {
  if (!text) return ''
  const cleaned = text.replace(/\s+/g, ' ').trim()
  if (cleaned.length <= maxLength) return cleaned
  return cleaned.slice(0, maxLength - 3) + '...'
}

export default GraphCanvas
