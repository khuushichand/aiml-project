import { Button, Empty } from "antd"
import { Plus, Kanban } from "lucide-react"

import type { Board } from "@/types/kanban"

interface BoardGalleryProps {
  boards: Board[]
  onSelectBoard: (boardId: number) => void
  onCreateBoard: () => void
}

export const BoardGallery = ({
  boards,
  onSelectBoard,
  onCreateBoard
}: BoardGalleryProps) => {
  const activeBoards = boards.filter((b) => !b.archived)
  const archivedBoards = boards.filter((b) => b.archived)

  if (activeBoards.length === 0 && archivedBoards.length === 0) {
    return (
      <Empty
        description="Organize research tasks, track projects with boards and cards."
        className="mt-20"
      >
        <Button
          type="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={onCreateBoard}
        >
          Create Board
        </Button>
      </Empty>
    )
  }

  return (
    <div className="space-y-6">
      {/* Active boards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {activeBoards.map((board) => (
          <button
            key={board.id}
            onClick={() => onSelectBoard(board.id)}
            className="text-left bg-surface hover:bg-surface2 rounded-lg p-4 border border-transparent hover:border-primary/30 transition-colors cursor-pointer"
          >
            <div className="flex items-start gap-2 mb-2">
              <Kanban className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
              <h3 className="font-medium text-sm line-clamp-2">{board.name}</h3>
            </div>
            {board.description && (
              <p className="text-xs text-text-muted line-clamp-2 mb-2">
                {board.description}
              </p>
            )}
            <div className="text-xs text-text-subtle">
              Updated{" "}
              {new Date(board.updated_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric"
              })}
            </div>
          </button>
        ))}

        {/* Create board card */}
        <button
          onClick={onCreateBoard}
          className="flex items-center justify-center gap-2 bg-transparent border-2 border-dashed border-border hover:border-primary/50 rounded-lg p-4 text-text-muted hover:text-text transition-colors cursor-pointer min-h-[100px]"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm">New Board</span>
        </button>
      </div>

      {/* Archived boards (collapsed) */}
      {archivedBoards.length > 0 && (
        <details className="text-sm">
          <summary className="text-text-muted cursor-pointer hover:text-text">
            {archivedBoards.length} archived board
            {archivedBoards.length !== 1 ? "s" : ""}
          </summary>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-3">
            {archivedBoards.map((board) => (
              <button
                key={board.id}
                onClick={() => onSelectBoard(board.id)}
                className="text-left bg-surface/50 hover:bg-surface rounded-lg p-4 opacity-60 hover:opacity-100 transition-opacity cursor-pointer"
              >
                <div className="flex items-start gap-2 mb-1">
                  <Kanban className="w-4 h-4 text-text-muted mt-0.5 flex-shrink-0" />
                  <h3 className="font-medium text-sm line-clamp-1">
                    {board.name}
                  </h3>
                </div>
                <div className="text-xs text-text-subtle">Archived</div>
              </button>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
