import { UserCircle2 } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useMemo, useState, useEffect } from "react"
import { Tooltip } from "antd"
import { createImageDataUrl } from "@/utils/image-utils"

interface CharacterGalleryCardProps {
  character: {
    id?: string
    slug?: string
    name?: string
    avatar_url?: string
    image_base64?: string
  }
  onClick: () => void
}

export function CharacterGalleryCard({
  character,
  onClick
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

  return (
    <button
      type="button"
      className="group flex w-full flex-col items-center gap-2 rounded-lg border border-border bg-surface p-3 transition-all hover:border-primary/30 hover:bg-surface2 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2 focus:ring-offset-bg"
      onClick={onClick}
      aria-label={t("settings:manageCharacters.gallery.clickToPreview", {
        defaultValue: "Click to preview {{name}}",
        name: displayName
      })}
    >
      {/* Avatar */}
      <div className="relative aspect-square w-full max-w-[120px]">
        {avatarSrc && !avatarImgError ? (
          <img
            src={avatarSrc}
            alt={displayName}
            className="h-full w-full rounded-lg object-cover ring-2 ring-border group-hover:ring-primary/30"
            onError={() => setAvatarImgError(true)}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center rounded-lg bg-surface2 ring-2 ring-border group-hover:ring-primary/30">
            <UserCircle2 className="h-16 w-16 text-text-subtle" />
          </div>
        )}
      </div>

      {/* Name */}
      <Tooltip title={displayName} placement="bottom">
        <span className="w-full truncate text-center text-sm font-medium text-text group-hover:text-primary">
          {displayName}
        </span>
      </Tooltip>
    </button>
  )
}
