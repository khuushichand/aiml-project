import type { DocumentType } from "./types"

const PDF_EXTENSIONS = [".pdf"]
const EPUB_EXTENSIONS = [".epub"]

const inferFromFilename = (filename?: string): DocumentType | null => {
  if (!filename) return null
  const name = filename.toLowerCase()
  if (PDF_EXTENSIONS.some((ext) => name.endsWith(ext))) return "pdf"
  if (EPUB_EXTENSIONS.some((ext) => name.endsWith(ext))) return "epub"
  return null
}

export const inferDocumentTypeFromMedia = (
  mediaType?: string,
  filename?: string
): DocumentType | null => {
  const type = String(mediaType || "").toLowerCase()
  if (type.includes("pdf")) return "pdf"
  if (type.includes("epub") || type.includes("ebook")) return "epub"
  return inferFromFilename(filename)
}

export const getDocumentMimeType = (docType: DocumentType): string =>
  docType === "pdf" ? "application/pdf" : "application/epub+zip"
