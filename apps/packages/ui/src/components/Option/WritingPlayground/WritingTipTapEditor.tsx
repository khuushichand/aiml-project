import { useCallback, useEffect, useMemo } from "react"
import { EditorContent, useEditor, type JSONContent } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import Placeholder from "@tiptap/extension-placeholder"
import CharacterCount from "@tiptap/extension-character-count"
import { SceneBreakExtension } from "./extensions/SceneBreakExtension"
import { CitationExtension } from "./extensions/CitationExtension"
import { tipTapJsonToPlainText } from "./writing-tiptap-utils"

export type WritingTipTapEditorProps = {
  content: JSONContent | null
  onContentChange: (json: JSONContent, plainText: string) => void
  editable?: boolean
  placeholder?: string
  className?: string
}

export function WritingTipTapEditor({
  content,
  onContentChange,
  editable = true,
  placeholder = "Start writing...",
  className,
}: WritingTipTapEditorProps) {
  const extensions = useMemo(
    () => [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      SceneBreakExtension,
      CitationExtension,
      Placeholder.configure({ placeholder }),
      CharacterCount,
    ],
    [placeholder],
  )

  const handleUpdate = useCallback(
    ({ editor }: { editor: any }) => {
      const json = editor.getJSON() as JSONContent
      const plain = tipTapJsonToPlainText(json)
      onContentChange(json, plain)
    },
    [onContentChange],
  )

  const editor = useEditor({
    extensions,
    content: content || { type: "doc", content: [{ type: "paragraph" }] },
    editable,
    onUpdate: handleUpdate,
  })

  // Sync content from parent (e.g., when switching scenes)
  useEffect(() => {
    if (editor && content && !editor.isFocused) {
      const currentJson = JSON.stringify(editor.getJSON())
      const newJson = JSON.stringify(content)
      if (currentJson !== newJson) {
        editor.commands.setContent(content)
      }
    }
  }, [editor, content])

  // Sync editable state
  useEffect(() => {
    if (editor) {
      editor.setEditable(editable)
    }
  }, [editor, editable])

  if (!editor) return null

  return (
    <div className={className}>
      <EditorContent
        editor={editor}
        className="prose prose-sm max-w-none min-h-[300px] focus:outline-none p-4"
      />
    </div>
  )
}

export default WritingTipTapEditor
