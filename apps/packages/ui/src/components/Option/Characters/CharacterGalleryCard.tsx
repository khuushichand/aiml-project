import { MessageCircle } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useMemo, useState, useEffect } from "react"
import { Tooltip } from "antd"
import { createImageDataUrl } from "@/utils/image-utils"

export type GalleryCardDensity = "rich" | "compact"

const DEFAULT_FALLBACK_NAME = "character"

const getInitialCharacter = (value: string): string => {
  const match = value.match(/[A-Za-z0-9]/)
  return match ? match[0].toUpperCase() : "?"
}

export const hashNameToHue = (name: string): number => {
  let hash = 0
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0
  }
  return Math.abs(hash) % 360
}

export const getAvatarFallbackTokens = (name?: string) => {
  const normalized = (name || DEFAULT_FALLBACK_NAME).trim().toLowerCase()
  const hue = hashNameToHue(normalized || DEFAULT_FALLBACK_NAME)
  return {
    hue,
    initial: getInitialCharacter(name || ""),
    backgroundColor: `hsl(${hue} 68% 82%)`,
    color: `hsl(${hue} 45% 20%)`
  }
}

interface CharacterGalleryCardProps {
  character: {
    id?: string
    slug?: string
    name?: string
    description?: string
    tags?: string[]
    avatar_url?: string
    image_base64?: string
  }
  onClick: () => void
  conversationCount?: number
  density?: GalleryCardDensity
}

export function CharacterGalleryCard({
  character,
  onClick,
  conversationCount,
  density = "rich"
}: CharacterGalleryCardProps) {
  const { t } = useTranslation(["settings"])
  const [avatarImgError, setAvatarImgError] = useState(false)

  const avatarSrc = useMemo(() => {
    if (character.avatar_url) return character.avatar_url
    if (character.image_base64) return createImageDataUrl(character.image_base64)
    return null
  }, [character.avatar_url, character.image_base64])

  useEffect(() => {
    setAvatarImgError(false)
  }, [avatarSrc])

  const displayName =
    character.name ||
    t("settings:manageCharacters.preview.untitled", {
      defaultValue: "Untitled character"
    })
  const displayDescription = (character.description || "").trim()
  const displayTags = (character.tags || []).filter((tag) => tag.trim().length > 0).slice(0, 3)
  const isCompact = density === "compact"
  const fallbackTokens = useMemo(
    () => getAvatarFallbackTokens(displayName),
    [displayName]
  )

  return (
    <button
      type="button"
      className={`group flex w-full flex-col items-center gap-2 rounded-lg border border-border bg-surface p-3 transition-all motion-reduce:transition-none hover:border-primary/30 hover:bg-surface2 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2 focus:ring-offset-bg ${
        isCompact ? "min-h-[168px]" : "min-h-[220px]"
      }`}
      onClick={onClick}
      aria-label={t("settings:manageCharacters.gallery.clickToPreview", {
        defaultValue: "Click to preview {{name}}",
        name: displayName
      })}
    >
      {/* Avatar */}
      <div
        className={`relative aspect-square w-full ${
          isCompact ? "max-w-[102px]" : "max-w-[120px]"
        }`}>
        {avatarSrc && !avatarImgError ? (
          <img
            src={avatarSrc}
            alt={displayName}
            loading="lazy"
            decoding="async"
            className="h-full w-full rounded-lg object-cover ring-2 ring-border group-hover:ring-primary/30"
            onError={() => setAvatarImgError(true)}
          />
        ) : (
          <div
            data-testid="character-gallery-fallback-avatar"
            className="flex h-full w-full items-center justify-center rounded-lg ring-2 ring-border/70 group-hover:ring-primary/30"
            style={{
              backgroundColor: fallbackTokens.backgroundColor,
              color: fallbackTokens.color
            }}>
            <span className="text-3xl font-semibold leading-none">
              {fallbackTokens.initial}
            </span>
          </div>
        )}
        {/* Conversation count badge */}
        {typeof conversationCount === 'number' && conversationCount > 0 && (
          <Tooltip
            title={t("settings:manageCharacters.gallery.conversationCount", {
              defaultValue: "{{count}} conversation(s)",
              count: conversationCount
            })}
          >
            <div className="absolute -bottom-1 -right-1 flex items-center gap-0.5 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-medium text-white shadow-sm">
              <MessageCircle className="h-3 w-3" />
              <span>{conversationCount > 99 ? '99+' : conversationCount}</span>
            </div>
          </Tooltip>
        )}
      </div>

      {/* Name */}
      <Tooltip title={displayName} placement="bottom">
        <span className="w-full truncate text-center text-sm font-medium text-text group-hover:text-primary">
          {displayName}
        </span>
      </Tooltip>

      {!isCompact && displayDescription && (
        <Tooltip title={displayDescription} placement="bottom">
          <p className="w-full line-clamp-2 text-center text-xs leading-5 text-text-muted">
            {displayDescription}
          </p>
        </Tooltip>
      )}

      {!isCompact && displayTags.length > 0 && (
        <div className="mt-0.5 flex w-full flex-wrap justify-center gap-1">
          {displayTags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-border/80 bg-surface2 px-2 py-0.5 text-[10px] font-medium text-text-muted">
              {tag}
            </span>
          ))}
        </div>
      )}
    </button>
  )
}
