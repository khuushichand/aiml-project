import { useEffect, useState, type FC, type ReactNode } from "react"
import { Drawer } from "antd"
import {
  resolveWritingLayoutMode,
  type WritingLayoutMode
} from "./writing-layout-utils"

type WritingPlaygroundShellProps = {
  children: ReactNode
  libraryOpen: boolean
  inspectorOpen: boolean
  onLibraryToggle: () => void
  onInspectorToggle: () => void
  libraryContent: ReactNode
  inspectorContent: ReactNode
}

export const WritingPlaygroundShell: FC<WritingPlaygroundShellProps> = ({
  children,
  libraryOpen,
  inspectorOpen,
  onLibraryToggle,
  onInspectorToggle,
  libraryContent,
  inspectorContent
}) => {
  const [layoutMode, setLayoutMode] = useState<WritingLayoutMode>(() => {
    if (typeof window === "undefined") return "expanded"
    return resolveWritingLayoutMode(window.innerWidth)
  })

  useEffect(() => {
    if (typeof window === "undefined") return
    const onResize = () => {
      setLayoutMode(resolveWritingLayoutMode(window.innerWidth))
    }
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])

  const isCompact = layoutMode === "compact"

  return (
    <div
      data-testid="writing-playground-shell"
      data-layout-mode={layoutMode}
      className="flex h-full w-full overflow-hidden">
      {/* Pinned library sidebar for expanded mode */}
      {!isCompact && libraryOpen && (
        <div
          data-testid="writing-library-sidebar"
          className="w-[280px] flex-shrink-0 border-r border-border overflow-y-auto bg-surface">
          {libraryContent}
        </div>
      )}

      {/* Compact mode library drawer */}
      {isCompact && (
        <Drawer
          title="Sessions"
          placement="left"
          open={libraryOpen}
          onClose={onLibraryToggle}
          width={320}
          styles={{ body: { padding: 0 } }}>
          {libraryContent}
        </Drawer>
      )}

      {/* Main editor area fills remaining space */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {children}
      </div>

      {/* Pinned inspector sidebar for expanded mode */}
      {!isCompact && inspectorOpen && (
        <div
          data-testid="writing-inspector-sidebar"
          className="w-[320px] flex-shrink-0 border-l border-border overflow-y-auto bg-surface">
          {inspectorContent}
        </div>
      )}

      {/* Compact mode inspector drawer */}
      {isCompact && (
        <Drawer
          title="Settings"
          placement="right"
          open={inspectorOpen}
          onClose={onInspectorToggle}
          width={360}
          styles={{ body: { padding: 0 } }}>
          {inspectorContent}
        </Drawer>
      )}
    </div>
  )
}
