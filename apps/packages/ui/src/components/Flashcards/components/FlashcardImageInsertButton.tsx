import React from "react"
import { Button } from "antd"

import { uploadFlashcardAsset } from "@/services/flashcard-assets"

interface FlashcardImageInsertButtonProps {
  ariaLabel: string
  onInsert: (markdownSnippet: string) => void | Promise<void>
  onError?: (error: Error) => void
  buttonLabel?: string
  disabled?: boolean
}

export const FlashcardImageInsertButton: React.FC<FlashcardImageInsertButtonProps> = ({
  ariaLabel,
  onInsert,
  onError,
  buttonLabel = "Insert image",
  disabled = false
}) => {
  const inputRef = React.useRef<HTMLInputElement | null>(null)
  const [isUploading, setIsUploading] = React.useState(false)

  const handleChange = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      event.target.value = ""
      if (!file) return
      setIsUploading(true)
      try {
        const asset = await uploadFlashcardAsset(file)
        await onInsert(asset.markdown_snippet)
      } catch (error: unknown) {
        onError?.(error instanceof Error ? error : new Error("Image upload failed."))
      } finally {
        setIsUploading(false)
      }
    },
    [onError, onInsert]
  )

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        aria-label={ariaLabel}
        className="sr-only"
        onChange={handleChange}
      />
      <Button
        size="small"
        type="text"
        disabled={disabled}
        loading={isUploading}
        onMouseDown={(event) => event.preventDefault()}
        onClick={(event) => {
          event.preventDefault()
          event.stopPropagation()
          inputRef.current?.click()
        }}
      >
        {buttonLabel}
      </Button>
    </>
  )
}

export default FlashcardImageInsertButton
