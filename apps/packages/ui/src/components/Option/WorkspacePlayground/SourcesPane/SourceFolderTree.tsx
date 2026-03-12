import React from "react"
import { Checkbox } from "antd"
import type { FolderSelectionState } from "@/store/workspace-organization"

export interface SourceFolderTreeNode {
  id: string
  name: string
  sourceCount: number
  children: SourceFolderTreeNode[]
}

interface SourceFolderTreeProps {
  nodes: SourceFolderTreeNode[]
  activeFolderId: string | null
  selectionStateByFolderId: Record<string, FolderSelectionState>
  onFocusFolder: (folderId: string) => void
  onToggleFolderSelection: (folderId: string) => void
}

const renderNode = (
  node: SourceFolderTreeNode,
  depth: number,
  activeFolderId: string | null,
  selectionStateByFolderId: Record<string, FolderSelectionState>,
  onFocusFolder: (folderId: string) => void,
  onToggleFolderSelection: (folderId: string) => void
): React.ReactElement => {
  const selectionState = selectionStateByFolderId[node.id] || "unchecked"
  const isActive = activeFolderId === node.id

  return (
    <div key={node.id} className="space-y-1">
      <div
        className={`flex items-center gap-2 rounded-md px-2 py-1 ${
          isActive ? "bg-primary/10" : "hover:bg-surface2"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <Checkbox
          aria-label={`Select folder ${node.name}`}
          checked={selectionState === "checked"}
          indeterminate={selectionState === "indeterminate"}
          onChange={() => onToggleFolderSelection(node.id)}
        />
        <button
          type="button"
          aria-label={`Focus folder ${node.name}`}
          className={`min-w-0 flex-1 truncate text-left text-sm ${
            isActive ? "font-medium text-primary" : "text-text"
          }`}
          onClick={() => onFocusFolder(node.id)}
        >
          {node.name}
        </button>
        <span className="shrink-0 text-[11px] text-text-muted">
          {node.sourceCount}
        </span>
      </div>
      {node.children.map((child) =>
        renderNode(
          child,
          depth + 1,
          activeFolderId,
          selectionStateByFolderId,
          onFocusFolder,
          onToggleFolderSelection
        )
      )}
    </div>
  )
}

export const SourceFolderTree: React.FC<SourceFolderTreeProps> = ({
  nodes,
  activeFolderId,
  selectionStateByFolderId,
  onFocusFolder,
  onToggleFolderSelection
}) => {
  if (nodes.length === 0) {
    return null
  }

  return (
    <div
      className="rounded-lg border border-border/70 bg-surface/60 p-2"
      aria-label="Source folders"
    >
      <div className="mb-2 flex items-center justify-between px-2 text-xs font-semibold uppercase tracking-[0.08em] text-text-muted">
        <span>Folders</span>
      </div>
      <div className="space-y-1">
        {nodes.map((node) =>
          renderNode(
            node,
            0,
            activeFolderId,
            selectionStateByFolderId,
            onFocusFolder,
            onToggleFolderSelection
          )
        )}
      </div>
    </div>
  )
}
