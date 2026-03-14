import React from "react"

import {
  acquireFlashcardAssetObjectUrl,
  releaseFlashcardAssetObjectUrl
} from "@/services/flashcard-assets"

interface ManagedMarkdownImageProps {
  assetUuid: string
  alt?: string
  className?: string
}

export const ManagedMarkdownImage: React.FC<ManagedMarkdownImageProps> = ({
  assetUuid,
  alt,
  className = "my-2 max-w-full rounded-md border border-border"
}) => {
  const [src, setSrc] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let mounted = true
    setSrc(null)
    setError(null)

    void acquireFlashcardAssetObjectUrl(assetUuid)
      .then((objectUrl) => {
        if (!mounted) return
        setSrc(objectUrl)
      })
      .catch((err: unknown) => {
        if (!mounted) return
        setError(err instanceof Error ? err.message : "Unable to load image.")
      })

    return () => {
      mounted = false
      releaseFlashcardAssetObjectUrl(assetUuid)
    }
  }, [assetUuid])

  if (error) {
    return (
      <span className="inline-flex items-center gap-2 rounded-md border border-border bg-surface2 px-2 py-1 text-[11px] text-text-muted">
        {`Image unavailable: ${alt || "Flashcard image"}`}
      </span>
    )
  }

  if (!src) {
    return (
      <span className="inline-flex items-center gap-2 rounded-md border border-border bg-surface2 px-2 py-1 text-[11px] text-text-muted">
        Loading image...
      </span>
    )
  }

  return (
    <img
      src={src}
      alt={alt || ""}
      loading="lazy"
      className={className}
    />
  )
}

export default ManagedMarkdownImage
