import { useEffect, useState, type FC } from "react"
import type { WritingPlaygroundShellProps } from "./WritingPlayground.types"
import {
  resolveWritingLayoutMode,
  type WritingLayoutMode
} from "./writing-layout-utils"

export const WritingPlaygroundShell: FC<WritingPlaygroundShellProps> = ({
  children
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

  return (
    <div
      data-testid="writing-playground-shell"
      data-layout-mode={layoutMode}
      className={
        layoutMode === "compact"
          ? "writing-playground-shell-compact [&_.writing-playground-grid-main]:!grid-cols-1 [&_.writing-playground-grid-main]:!gap-4 [&_.writing-playground-grid-side]:!grid-cols-1 [&_.writing-playground-grid-side]:!gap-4"
          : "writing-playground-shell-expanded"
      }>
      {children}
    </div>
  )
}
