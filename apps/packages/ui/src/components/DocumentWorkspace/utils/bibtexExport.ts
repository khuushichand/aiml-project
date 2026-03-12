/**
 * BibTeX export utilities for document references.
 */

interface BibTeXReference {
  title: string
  authors?: string | string[]
  year?: number | string
  venue?: string
  doi?: string
  url?: string
  arxivId?: string
}

/**
 * Convert a reference to BibTeX format.
 */
export function referenceToBibTeX(ref: BibTeXReference, index: number): string {
  // Generate cite key from first author's last name + year
  let citeKey = "ref"
  const authorList =
    typeof ref.authors === "string"
      ? ref.authors.split(",").map((a) => a.trim())
      : ref.authors
  if (authorList && authorList.length > 0) {
    const firstAuthor = authorList[0].trim().split(" ")
    citeKey = (firstAuthor[firstAuthor.length - 1] || "ref").toLowerCase()
  }
  citeKey += ref.year ? String(ref.year) : ""
  // Ensure uniqueness with index suffix
  citeKey += `_${index + 1}`

  const lines: string[] = []
  lines.push(`@article{${citeKey},`)

  // Title
  lines.push(`  title = {${ref.title}},`)

  // Authors
  if (authorList && authorList.length > 0) {
    lines.push(`  author = {${authorList.join(" and ")}},`)
  }

  // Year
  if (ref.year) {
    lines.push(`  year = {${ref.year}},`)
  }

  // Venue/Journal
  if (ref.venue) {
    lines.push(`  journal = {${ref.venue}},`)
  }

  // DOI
  if (ref.doi) {
    lines.push(`  doi = {${ref.doi}},`)
  }

  // URL
  if (ref.url) {
    lines.push(`  url = {${ref.url}},`)
  } else if (ref.arxivId) {
    lines.push(`  url = {https://arxiv.org/abs/${ref.arxivId}},`)
  }

  lines.push("}")

  return lines.join("\n")
}

/**
 * Export an array of references as a .bib file download.
 */
export function exportReferencesBibTeX(
  refs: BibTeXReference[],
  documentTitle: string
): void {
  const header = `% BibTeX export from "${documentTitle}"\n% Generated ${new Date().toISOString()}\n\n`
  const entries = refs.map((ref, index) => referenceToBibTeX(ref, index))
  const content = header + entries.join("\n\n") + "\n"

  const blob = new Blob([content], { type: "application/x-bibtex" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  const safeTitle = documentTitle
    .replace(/[^a-zA-Z0-9_-]/g, "_")
    .slice(0, 50)
  link.download = `${safeTitle}_references.bib`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
