import { Mark, mergeAttributes } from "@tiptap/core"

export const CitationExtension = Mark.create({
  name: "citation",

  addAttributes() {
    return {
      sourceId: { default: null },
      sourceTitle: { default: null },
      sourceType: { default: null },
    }
  },

  parseHTML() {
    return [{ tag: "span[data-citation]" }]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-citation": "",
        class: "citation-mark",
        style:
          "background: rgba(59, 130, 246, 0.1); border-bottom: 1px dashed #3b82f6; cursor: pointer; padding: 0 2px;",
        title: HTMLAttributes.sourceTitle || "Citation",
      }),
      0,
    ]
  },
})
