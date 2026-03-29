import React from "react"
import { Button } from "antd"
import { useTranslation } from "react-i18next"
import NotesStudioDiagramCard from "./NotesStudioDiagramCard"
import type {
  NoteStudioDocument,
  NoteStudioPayload,
  NoteStudioSectionPayload,
  NoteStudioNote,
  NotesStudioHandwritingMode,
  NotesStudioPaperSize,
  NotesStudioTemplateType
} from "./notes-studio-types"

interface NotesStudioViewProps {
  note: NoteStudioNote
  studioDocument: NoteStudioDocument
  isStale: boolean
  staleReason?: string | null
  paperSize: NotesStudioPaperSize
  onPaperSizeChange: (paperSize: NotesStudioPaperSize) => void
  onRegenerate: () => void
  regenerating?: boolean
  onContinueEditingPlainNote?: () => void
}

const PAPER_SIZE_OPTIONS: NotesStudioPaperSize[] = ["US Letter", "A4", "A5"]

const asStudioPayload = (value: unknown): NoteStudioPayload => {
  if (!value || typeof value !== "object") {
    return { layout: null, sections: [] }
  }
  return value as NoteStudioPayload
}

const normalizeSections = (value: unknown): NoteStudioSectionPayload[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => (entry && typeof entry === "object" ? (entry as NoteStudioSectionPayload) : null))
    .filter((entry): entry is NoteStudioSectionPayload => Boolean(entry?.id))
}

const sectionBodyClassName = (kind: string): string => {
  if (kind === "cue") return "studio-cue-section"
  if (kind === "summary") return "studio-summary-section"
  if (kind === "notes") return "studio-notes-section"
  if (kind === "prompt") return "studio-prompt-section"
  return "studio-generic-section"
}

const notesBodyText = (section: NoteStudioSectionPayload): string => {
  if (typeof section.content === "string") return section.content
  if (Array.isArray(section.items)) return section.items.join("\n")
  return ""
}

const NotesStudioView: React.FC<NotesStudioViewProps> = ({
  note,
  studioDocument,
  isStale,
  staleReason = null,
  paperSize,
  onPaperSizeChange,
  onRegenerate,
  regenerating = false,
  onContinueEditingPlainNote
}) => {
  const { t } = useTranslation(["option", "common"])
  const payload = asStudioPayload(studioDocument.payload_json)
  const layout = payload.layout ?? {}
  const sections = normalizeSections(payload.sections)
  const templateType: NotesStudioTemplateType = layout.template_type ?? studioDocument.template_type
  const handwritingMode: NotesStudioHandwritingMode =
    layout.handwriting_mode ?? studioDocument.handwriting_mode
  const hasAccent = handwritingMode === "accented"
  const handwritingAccentStyle = hasAccent
    ? {
        fontFamily: `"Patrick Hand", "Comic Sans MS", "Bradley Hand", "Segoe Print", cursive`,
        letterSpacing: "0.01em"
      }
    : undefined
  const sheetStyle: React.CSSProperties =
    templateType === "grid"
      ? {
          backgroundColor: "#fffdf8",
          backgroundImage:
            "linear-gradient(rgba(148, 163, 184, 0.22) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.22) 1px, transparent 1px)",
          backgroundSize: "24px 24px"
        }
      : templateType === "cornell"
        ? {
            backgroundColor: "#fffdf8",
            backgroundImage:
              "linear-gradient(to right, rgba(148, 163, 184, 0.12) 0, rgba(148, 163, 184, 0.12) 28%, transparent 28%)"
          }
        : {
            backgroundColor: "#fffdf8",
            backgroundImage:
              "linear-gradient(to bottom, rgba(59, 130, 246, 0.16) 1px, transparent 1px)",
            backgroundSize: "100% 30px"
          }
  const sectionsStyle: React.CSSProperties =
    templateType === "cornell"
      ? {
          display: "grid",
          gridTemplateColumns: "minmax(160px, 0.9fr) minmax(0, 2fr)",
          gap: "12px"
        }
      : {}

  return (
    <section
      className={`notes-studio-view studio-sheet studio-template-${templateType} rounded-lg border border-border bg-surface p-4`}
      data-testid="notes-studio-view"
      style={sheetStyle}
    >
      <div className={`sr-only studio-template-marker studio-template-${templateType}`} data-testid={`notes-studio-template-${templateType}`}>
        {templateType}
      </div>

      {isStale ? (
        <div
          className="notes-studio-stale-banner mb-4 rounded border border-warn/40 bg-warn/10 p-3 text-sm text-warn"
          data-testid="notes-studio-stale-banner"
        >
          <div>
            {t("option:notesSearch.notesStudioStaleWarning", {
              defaultValue:
                "This Studio view is stale because the markdown companion changed."
            })}
          </div>
          {staleReason ? <div className="mt-1 text-xs opacity-80">{staleReason}</div> : null}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              size="small"
              type="primary"
              loading={regenerating}
              onClick={onRegenerate}
            >
              {t("option:notesSearch.notesStudioRegenerateAction", {
                defaultValue: "Regenerate Studio view from current Markdown"
              })}
            </Button>
            <Button
              size="small"
              type="default"
              onClick={onContinueEditingPlainNote}
            >
              {t("option:notesSearch.notesStudioContinuePlainAction", {
                defaultValue: "Continue editing plain note"
              })}
            </Button>
          </div>
        </div>
      ) : null}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2
          className={`studio-heading text-lg font-semibold text-text ${hasAccent ? "studio-handwriting-accent" : ""}`}
          data-testid="notes-studio-heading"
          style={handwritingAccentStyle}
        >
          {note.title || t("option:notesSearch.untitledNote", { defaultValue: "Untitled note" })}
        </h2>
        <div className="flex items-center gap-2">
          <Button
            size="small"
            type="default"
            onClick={onContinueEditingPlainNote}
          >
            {t("option:notesSearch.notesStudioContinuePlainAction", {
              defaultValue: "Continue editing plain note"
            })}
          </Button>
          <label className="text-xs text-text-muted" htmlFor="notes-studio-paper-size-select">
            {t("option:notesSearch.notesStudioPaperSizeLabel", {
              defaultValue: "Paper size"
            })}
          </label>
          <select
            id="notes-studio-paper-size-select"
            className="min-w-[120px] rounded border border-border bg-surface px-2 py-1 text-sm text-text"
            value={paperSize}
            onChange={(event) => onPaperSizeChange(event.target.value as NotesStudioPaperSize)}
            data-testid="notes-studio-paper-size-select"
          >
            {PAPER_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div
        className={`studio-sections ${templateType === "cornell" ? "studio-cornell-layout" : ""} space-y-3`}
        data-testid="notes-studio-sections"
        style={sectionsStyle}
      >
        {sections.map((section) => {
          const sectionTitle = String(section.title || "")
          const cueItems = Array.isArray(section.items)
            ? section.items.map((item) => String(item || "")).filter((item) => item.length > 0)
            : []
          const bodyText = notesBodyText(section)
          const headingAccentClass = hasAccent ? "studio-handwriting-accent" : ""
          const cueAccentClass = hasAccent && section.kind === "cue" ? "studio-handwriting-accent" : ""
          const promptAccentClass =
            hasAccent && section.kind === "prompt" ? "studio-handwriting-accent" : ""
          const sectionStyle: React.CSSProperties =
            templateType === "cornell"
              ? section.kind === "cue"
                ? { gridColumn: "1" }
                : section.kind === "notes"
                  ? { gridColumn: "2" }
                  : { gridColumn: "1 / span 2" }
              : {}

          return (
            <article
              key={section.id}
              className={`studio-section ${sectionBodyClassName(section.kind)} rounded border border-border bg-surface2 p-3`}
              data-testid={`notes-studio-section-${section.id}`}
              style={sectionStyle}
            >
              {sectionTitle ? (
                <h3
                  className={`studio-section-title mb-2 text-sm font-semibold text-text ${headingAccentClass}`}
                  data-testid={`notes-studio-section-title-${section.id}`}
                  style={handwritingAccentStyle}
                >
                  {sectionTitle}
                </h3>
              ) : null}
              {cueItems.length > 0 ? (
                <ul className="space-y-1">
                  {cueItems.map((item, index) => (
                    <li
                      key={`${section.id}-${index}`}
                      className={`studio-cue-item text-sm text-text ${cueAccentClass}`}
                      data-testid={`notes-studio-cue-item-${section.id}-${index}`}
                      style={cueAccentClass ? handwritingAccentStyle : undefined}
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              ) : null}
              {bodyText ? (
                <p
                  className={`studio-section-content whitespace-pre-wrap text-sm leading-6 text-text ${promptAccentClass}`}
                  data-testid={`notes-studio-section-content-${section.id}`}
                  style={promptAccentClass ? handwritingAccentStyle : undefined}
                >
                  {bodyText}
                </p>
              ) : null}
            </article>
          )
        })}
      </div>

      <div className="mt-4">
        <NotesStudioDiagramCard manifest={studioDocument.diagram_manifest_json} />
      </div>
    </section>
  )
}

export default NotesStudioView
