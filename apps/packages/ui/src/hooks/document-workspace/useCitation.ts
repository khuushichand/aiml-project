import { useCallback, useMemo } from "react"
import { useDocumentMetadata } from "./useDocumentMetadata"

/**
 * Citation format options
 */
export type CitationFormat = "mla" | "apa" | "chicago" | "harvard" | "ieee"

/**
 * Citation format display information
 */
export const CITATION_FORMAT_INFO: Record<
  CitationFormat,
  { label: string; description: string }
> = {
  mla: {
    label: "MLA",
    description: "Modern Language Association (9th ed.)"
  },
  apa: {
    label: "APA",
    description: "American Psychological Association (7th ed.)"
  },
  chicago: {
    label: "Chicago",
    description: "Chicago Manual of Style (17th ed.)"
  },
  harvard: {
    label: "Harvard",
    description: "Harvard Referencing Style"
  },
  ieee: {
    label: "IEEE",
    description: "Institute of Electrical and Electronics Engineers"
  }
}

/**
 * Metadata required for citation generation
 */
interface CitationMetadata {
  title: string
  authors?: string[]
  date?: Date | string
  url?: string
  publisher?: string
  pages?: number
  doi?: string
  volume?: string
  issue?: string
}

/**
 * Format author names for MLA style (Last, First)
 */
function formatMlaAuthors(authors: string[]): string {
  if (authors.length === 0) return ""
  if (authors.length === 1) return authors[0]
  if (authors.length === 2) return `${authors[0]} and ${authors[1]}`
  return `${authors[0]}, et al.`
}

/**
 * Format author names for APA style (Last, F.)
 */
function formatApaAuthors(authors: string[]): string {
  if (authors.length === 0) return ""

  const formatted = authors.map((author) => {
    const parts = author.trim().split(" ")
    if (parts.length === 1) return parts[0]
    const lastName = parts[parts.length - 1]
    const initials = parts
      .slice(0, -1)
      .map((n) => n.charAt(0).toUpperCase() + ".")
      .join(" ")
    return `${lastName}, ${initials}`
  })

  if (formatted.length === 1) return formatted[0]
  if (formatted.length === 2) return `${formatted[0]} & ${formatted[1]}`
  if (formatted.length <= 20) {
    return formatted.slice(0, -1).join(", ") + ", & " + formatted[formatted.length - 1]
  }
  return formatted.slice(0, 19).join(", ") + ", ... " + formatted[formatted.length - 1]
}

/**
 * Format date for citations
 */
function formatDate(date: Date | string | undefined): {
  year: string
  full: string
  day: string
  month: string
} {
  if (!date) {
    return { year: "n.d.", full: "n.d.", day: "", month: "" }
  }

  const d = new Date(date)
  if (isNaN(d.getTime())) {
    return { year: "n.d.", full: "n.d.", day: "", month: "" }
  }

  const year = d.getFullYear().toString()
  const months = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ]
  const month = months[d.getMonth()]
  const day = d.getDate().toString()

  return {
    year,
    full: `${month} ${day}, ${year}`,
    day,
    month
  }
}

/**
 * Format citation in MLA style
 */
export function formatMLA(metadata: CitationMetadata): string {
  const parts: string[] = []

  // Author(s)
  if (metadata.authors && metadata.authors.length > 0) {
    parts.push(formatMlaAuthors(metadata.authors) + ".")
  }

  // Title in quotes
  parts.push(`"${metadata.title}."`)

  // Publisher/Container if available
  if (metadata.publisher) {
    parts.push(`${metadata.publisher},`)
  }

  // Date
  const date = formatDate(metadata.date)
  parts.push(date.full + ".")

  // URL if available
  if (metadata.url) {
    parts.push(metadata.url + ".")
  }

  return parts.join(" ")
}

/**
 * Format citation in APA style
 */
export function formatAPA(metadata: CitationMetadata): string {
  const parts: string[] = []

  // Author(s)
  if (metadata.authors && metadata.authors.length > 0) {
    parts.push(formatApaAuthors(metadata.authors))
  }

  // Year in parentheses
  const date = formatDate(metadata.date)
  parts.push(`(${date.year}).`)

  // Title in italics (represented without italics in plain text)
  parts.push(`${metadata.title}.`)

  // Publisher if available
  if (metadata.publisher) {
    parts.push(`${metadata.publisher}.`)
  }

  // DOI or URL
  if (metadata.doi) {
    parts.push(`https://doi.org/${metadata.doi}`)
  } else if (metadata.url) {
    parts.push(metadata.url)
  }

  return parts.join(" ")
}

/**
 * Format citation in Chicago style (Notes-Bibliography)
 */
export function formatChicago(metadata: CitationMetadata): string {
  const parts: string[] = []

  // Author(s)
  if (metadata.authors && metadata.authors.length > 0) {
    parts.push(metadata.authors.join(", ") + ".")
  }

  // Title in quotes
  parts.push(`"${metadata.title}."`)

  // Publisher if available
  if (metadata.publisher) {
    parts.push(metadata.publisher + ",")
  }

  // Date
  const date = formatDate(metadata.date)
  parts.push(date.year + ".")

  // URL if available
  if (metadata.url) {
    parts.push(metadata.url + ".")
  }

  return parts.join(" ")
}

/**
 * Format citation in Harvard style
 */
export function formatHarvard(metadata: CitationMetadata): string {
  const parts: string[] = []

  // Author(s) with year
  if (metadata.authors && metadata.authors.length > 0) {
    const date = formatDate(metadata.date)
    const firstAuthor = metadata.authors[0].split(" ").pop() || metadata.authors[0]
    if (metadata.authors.length > 1) {
      parts.push(`${firstAuthor} et al.`)
    } else {
      parts.push(firstAuthor)
    }
    parts.push(`(${date.year})`)
  }

  // Title
  parts.push(`'${metadata.title}',`)

  // Publisher if available
  if (metadata.publisher) {
    parts.push(`${metadata.publisher}.`)
  }

  // URL if available
  if (metadata.url) {
    const accessDate = formatDate(new Date()).full
    parts.push(`Available at: ${metadata.url} (Accessed: ${accessDate}).`)
  }

  return parts.join(" ")
}

/**
 * Format citation in IEEE style
 */
export function formatIEEE(metadata: CitationMetadata): string {
  const parts: string[] = []

  // Authors with initials first
  if (metadata.authors && metadata.authors.length > 0) {
    const formatted = metadata.authors.map((author) => {
      const nameParts = author.trim().split(" ")
      if (nameParts.length === 1) return nameParts[0]
      const lastName = nameParts[nameParts.length - 1]
      const initials = nameParts
        .slice(0, -1)
        .map((n) => n.charAt(0).toUpperCase() + ".")
        .join(" ")
      return `${initials} ${lastName}`
    })

    if (formatted.length <= 3) {
      parts.push(formatted.join(", ") + ",")
    } else {
      parts.push(formatted.slice(0, 3).join(", ") + " et al.,")
    }
  }

  // Title in quotes
  parts.push(`"${metadata.title},"`)

  // Publisher if available
  if (metadata.publisher) {
    parts.push(metadata.publisher + ",")
  }

  // Date
  const date = formatDate(metadata.date)
  parts.push(date.year + ".")

  // URL if available
  if (metadata.url) {
    parts.push(`[Online]. Available: ${metadata.url}`)
  }

  return parts.join(" ")
}

/**
 * Generate citation in the specified format
 */
export function generateCitation(
  metadata: CitationMetadata,
  format: CitationFormat
): string {
  switch (format) {
    case "mla":
      return formatMLA(metadata)
    case "apa":
      return formatAPA(metadata)
    case "chicago":
      return formatChicago(metadata)
    case "harvard":
      return formatHarvard(metadata)
    case "ieee":
      return formatIEEE(metadata)
  }
}

/**
 * Hook to generate citations for a document.
 *
 * Uses document metadata to generate citations in various formats.
 *
 * @param documentId - The document ID to generate citations for
 * @returns Citation generation utilities
 */
export function useCitation(documentId: number | null) {
  const { data: metadata, isLoading, error } = useDocumentMetadata(documentId)

  // Convert metadata to citation format
  const citationMetadata: CitationMetadata | null = useMemo(() => {
    if (!metadata) return null

    return {
      title: metadata.title || "Untitled Document",
      authors: metadata.authors,
      date: metadata.createdDate,
      url: undefined, // Would need to be added to metadata if available
      publisher: undefined
    }
  }, [metadata])

  // Generate citation in specified format
  const getCitation = useCallback(
    (format: CitationFormat): string => {
      if (!citationMetadata) {
        return "Citation unavailable - document metadata not loaded"
      }
      return generateCitation(citationMetadata, format)
    },
    [citationMetadata]
  )

  // Get all citations at once
  const getAllCitations = useCallback((): Record<CitationFormat, string> => {
    if (!citationMetadata) {
      const placeholder = "Citation unavailable"
      return {
        mla: placeholder,
        apa: placeholder,
        chicago: placeholder,
        harvard: placeholder,
        ieee: placeholder
      }
    }

    return {
      mla: formatMLA(citationMetadata),
      apa: formatAPA(citationMetadata),
      chicago: formatChicago(citationMetadata),
      harvard: formatHarvard(citationMetadata),
      ieee: formatIEEE(citationMetadata)
    }
  }, [citationMetadata])

  return {
    getCitation,
    getAllCitations,
    metadata: citationMetadata,
    isLoading,
    error
  }
}

export default useCitation
