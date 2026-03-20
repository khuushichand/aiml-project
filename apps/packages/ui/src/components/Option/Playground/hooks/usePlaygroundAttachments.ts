import React from "react"
import { toBase64 } from "~/libs/to-base64"
import { otherUnsupportedTypes } from "../../Knowledge/utils/unsupported-types"

// ---------------------------------------------------------------------------
// Deps interface
// ---------------------------------------------------------------------------

export interface UsePlaygroundAttachmentsDeps {
  /** Chat mode - images disabled in RAG mode */
  chatMode: string
  /** Form helpers */
  setFieldValue: (field: string, value: any) => void
  /** File upload handler from useMessageOption */
  handleFileUpload: (file: File) => Promise<void>
  /** Notification for disabled image */
  notifyImageAttachmentDisabled: () => void
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function usePlaygroundAttachments(deps: UsePlaygroundAttachmentsDeps) {
  const {
    chatMode,
    setFieldValue,
    handleFileUpload,
    notifyImageAttachmentDisabled
  } = deps

  const inputRef = React.useRef<HTMLInputElement>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const processedFilesRef = React.useRef<WeakSet<File>>(new WeakSet())

  const onFileInputChange = React.useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0]
        const isUnsupported = otherUnsupportedTypes.includes(file.type)
        if (isUnsupported) {
          console.error("File type not supported:", file.type)
          return
        }
        const isImage = file.type.startsWith("image/")
        if (isImage) {
          if (chatMode === "rag") {
            notifyImageAttachmentDisabled()
            return
          }
          const base64 = await toBase64(file)
          setFieldValue("image", base64)
        } else {
          await handleFileUpload(file)
        }
      }
    },
    [chatMode, handleFileUpload, notifyImageAttachmentDisabled, setFieldValue]
  )

  const onInputChange = React.useCallback(
    async (e: React.ChangeEvent<HTMLInputElement> | File) => {
      if (e instanceof File) {
        const isUnsupported = otherUnsupportedTypes.includes(e.type)
        if (isUnsupported) {
          console.error("File type not supported:", e.type)
          return
        }
        const isImage = e.type.startsWith("image/")
        if (isImage) {
          if (chatMode === "rag") {
            notifyImageAttachmentDisabled()
            return
          }
          const base64 = await toBase64(e)
          setFieldValue("image", base64)
        } else {
          await handleFileUpload(e)
        }
      } else {
        if (e.target.files) {
          onFileInputChange(e)
        }
      }
    },
    [chatMode, handleFileUpload, notifyImageAttachmentDisabled, onFileInputChange, setFieldValue]
  )

  const handleImageUpload = React.useCallback(() => {
    inputRef.current?.click()
  }, [])

  const handleDocumentUpload = React.useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  // Process dropped files
  const useDroppedFiles = (droppedFiles: File[]) => {
    React.useEffect(() => {
      if (droppedFiles.length === 0) return
      let cancelled = false
      const run = async () => {
        for (const file of droppedFiles) {
          if (cancelled) return
          if (processedFilesRef.current.has(file)) continue
          try {
            processedFilesRef.current.add(file)
            await onInputChange(file)
          } catch (error) {
            processedFilesRef.current.delete(file)
            console.error("Failed to process dropped file:", file.name, error)
          }
        }
      }
      void run()
      return () => {
        cancelled = true
      }
    }, [droppedFiles])
  }

  return {
    inputRef,
    fileInputRef,
    processedFilesRef,
    onFileInputChange,
    onInputChange,
    handleImageUpload,
    handleDocumentUpload,
    useDroppedFiles
  }
}
