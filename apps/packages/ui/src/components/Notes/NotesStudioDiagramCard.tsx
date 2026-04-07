import React from "react"
import DOMPurify from "dompurify"
import { useTranslation } from "react-i18next"
import type { NoteStudioDiagramManifest } from "./notes-studio-types"

interface NotesStudioDiagramCardProps {
  manifest?: NoteStudioDiagramManifest | null
}

const sanitizeSvg = (rawSvg: string): string =>
  DOMPurify.sanitize(rawSvg, {
    USE_PROFILES: {
      html: true,
      svg: true,
      svgFilters: true
    }
  })

const NotesStudioDiagramCard: React.FC<NotesStudioDiagramCardProps> = ({ manifest }) => {
  const { t } = useTranslation(["option"])
  const cachedSvg = typeof manifest?.cached_svg === "string" ? manifest.cached_svg : ""
  if (!cachedSvg.trim()) return null

  return (
    <section
      className="notes-studio-diagram-card rounded-lg border border-border bg-surface2 p-3"
      data-testid="notes-studio-diagram-card"
    >
      <h3 className="mb-2 text-sm font-semibold text-text">
        {t("option:notesSearch.notesStudioDiagramHeading", {
          defaultValue: "Diagram"
        })}
      </h3>
      <div
        className="notes-studio-diagram-svg overflow-x-auto rounded border border-border bg-surface p-2"
        data-testid="notes-studio-diagram-svg"
        dangerouslySetInnerHTML={{ __html: sanitizeSvg(cachedSvg) }}
      />
    </section>
  )
}

export default NotesStudioDiagramCard
