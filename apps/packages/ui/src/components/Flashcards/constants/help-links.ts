export const FLASHCARDS_HELP_DOC_BASE_URL =
  "https://github.com/rmusser01/tldw_server/blob/HEAD/Docs/User_Guides/Flashcards_Study_Guide.md"

const withAnchor = (anchor: string) => `${FLASHCARDS_HELP_DOC_BASE_URL}#${anchor}`

export const FLASHCARDS_HELP_LINKS = {
  overview: withAnchor("daily-study-workflow"),
  ratings: withAnchor("ratings-and-scheduling-basics"),
  cloze: withAnchor("cloze-syntax"),
  importFormats: withAnchor("import-and-export-formats"),
  troubleshooting: withAnchor("troubleshooting")
} as const

export default FLASHCARDS_HELP_LINKS
