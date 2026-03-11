import React from "react"
import { Button, Dropdown } from "antd"
import { List } from "lucide-react"

export interface ContentSection {
  id: string
  label: string
  offset: number
}

/**
 * Parse sections from content. Detects:
 * - Markdown headings (# H1, ## H2, etc.)
 * - Transcript timestamp boundaries (e.g., [00:05:30])
 */
export function parseSections(content: string): ContentSection[] {
  if (!content || content.trim().length === 0) return []

  const sections: ContentSection[] = []
  const lines = content.split("\n")
  let offset = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Markdown headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const text = headingMatch[2].trim()
      sections.push({
        id: `section-${i}`,
        label: `${"  ".repeat(level - 1)}${text}`,
        offset
      })
    }

    // Transcript timestamps like [00:05:30] or [1:30]
    const tsMatch = line.match(/^\s*\[(\d{1,2}:\d{2}(?::\d{2})?)\]/)
    if (tsMatch && !headingMatch) {
      // Only add timestamp sections every ~5 minutes or at significant gaps
      const timeStr = tsMatch[1]
      const parts = timeStr.split(":").map(Number)
      const totalSeconds =
        parts.length === 3
          ? parts[0] * 3600 + parts[1] * 60 + parts[2]
          : parts[0] * 60 + parts[1]

      // Add a section at every 5-minute boundary
      if (totalSeconds % 300 < 5 || sections.length === 0) {
        const restOfLine = line.replace(/^\s*\[\d{1,2}:\d{2}(?::\d{2})?\]\s*[-–—:]?\s*/, "").trim()
        const preview = restOfLine.slice(0, 40) + (restOfLine.length > 40 ? "…" : "")
        sections.push({
          id: `ts-${i}`,
          label: `[${timeStr}] ${preview}`,
          offset
        })
      }
    }

    offset += line.length + 1 // +1 for newline
  }

  return sections
}

interface SectionNavigatorProps {
  content: string
  onNavigate: (section: ContentSection) => void
  t: (key: string, fallback: string) => string
}

/**
 * Dropdown TOC for navigating long content with headings or transcript timestamps.
 */
export const SectionNavigator: React.FC<SectionNavigatorProps> = ({
  content,
  onNavigate,
  t
}) => {
  const sections = React.useMemo(() => parseSections(content), [content])

  if (sections.length < 2) return null

  return (
    <Dropdown
      menu={{
        items: sections.map((section) => ({
          key: section.id,
          label: section.label,
          onClick: () => onNavigate(section)
        }))
      }}
      trigger={["click"]}
    >
      <Button
        size="small"
        icon={<List className="w-3.5 h-3.5" />}
        data-testid="section-navigator"
      >
        {t("mediaPage.sections", "Sections")} ({sections.length})
      </Button>
    </Dropdown>
  )
}
