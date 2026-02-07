import React, { Suspense, lazy } from "react"
import { useNotesDockStore } from "@/store/notes-dock"

const NotesDockPanel = lazy(() =>
  import("./NotesDockPanel").then((m) => ({ default: m.NotesDockPanel }))
)

export const NotesDockHost: React.FC = () => {
  const isOpen = useNotesDockStore((state) => state.isOpen)

  if (!isOpen) return null

  return (
    <Suspense fallback={null}>
      <NotesDockPanel />
    </Suspense>
  )
}

export default NotesDockHost
